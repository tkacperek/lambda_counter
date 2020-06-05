import csv
import functools
import itertools
import multiprocessing
import os
import pathlib

import fire

import constants as const
import counters
import github_api
import local


class Main:
    def __init__(self, stop_after=None):
        self.stop_after = stop_after

    def handle(self, selector=None):
        parts = selector.split('/') if selector else []
        count = len(parts)
        if count == 1:
            return self.handle_language(*parts[:1])
        elif count == 3:
            return self.handle_repository(*parts[:3])
        elif count == 4:
            return self.handle_commit(*parts[:4])
        elif count > 4:
            return self.handle_file(parts[0], parts[2], ('/'.join(parts[4:]), -1))
        else:
            raise Exception('invalid selector')

    def handle_all(self):
        for language in const.LANGUAGES:
            self.handle_language(language)

    def handle_language(self, language):
        done_file = get_data_file(language, filename='done')
        if os.path.exists(done_file):
            return

        repositories = github_api.get_repositories(language, const.REPOSITORY_COUNT, get_data_file(language))
        if self.stop_after == 'get_repositories':
            return repositories

        for repository in repositories:
            self.handle_repository(language, *repository[1:3])

        pathlib.Path(done_file).touch()

    def handle_repository(self, language, owner, name):
        done_file = get_data_file(language, owner, name, filename='done')
        if os.path.exists(done_file):
            return

        local.clone_repository(owner, name)
        if self.stop_after == 'git_clone':
            return

        commits = local.get_commits(language, name, get_data_file(language, owner, name))
        if self.stop_after == 'get_commits':
            return commits

        previous_commit = None
        for date, commit_id in commits:
            self.handle_commit(language, owner, name, commit_id, previous_commit, date)
            previous_commit = commit_id

        local.delete_repository(name)

        self.make_repo_summary(f'{language}/{owner}/{name}')

        pathlib.Path(done_file).touch()

    def handle_commit(self, language, repository_owner, repository_name, commit, previous_commit=None, date=None):
        done_file = get_data_file(language, repository_owner, repository_name, commit, filename='done')
        if os.path.exists(done_file):
            return

        print(f'handling {language}/{repository_owner}/{repository_name}/{commit} ({date})')

        local.checkout_commit(repository_name, commit)
        if self.stop_after == 'git_checkout':
            return

        files = local.get_files(
            language,
            repository_name,
            commit,
            previous_commit,
            functools.partial(get_data_file, language, repository_owner, repository_name),
        )
        if self.stop_after == 'get_files':
            return files

        self._handle_files(language, repository_owner, repository_name, commit, files)

        pathlib.Path(done_file).touch()

    def _handle_files(self, language, repository_owner, repository_name, commit, files):
        with multiprocessing.Pool() as p:
            results = p.map(
                functools.partial(self.handle_file, language, repository_name),
                files,
                len(files) // os.cpu_count() + 1,
            )

        data_file = get_data_file(language, repository_owner, repository_name, commit)
        with open(data_file, 'w') as f:
            header = 'path,count\n'
            f.write(header)
            writer = csv.writer(f)
            writer.writerows([entry[0][0], entry[1][0]] for entry in zip(files, results))

        count, skipped = functools.reduce(
            lambda a, b: (a[0] + b[0], a[1] + b[1]),
            results,
        )

        samples = itertools.chain.from_iterable(r[2] for r in results)
        sample_file = get_data_file(language, repository_owner, repository_name, commit, filename='sample.txt')
        with open(sample_file, 'w') as f:
            for path, position, text in samples:
                f.writelines([
                    f'<sample path="{path}" position="{position}">\n',
                    text,
                    '\n</sample>\n',
                ])

        count_file = get_data_file(language, repository_owner, repository_name, commit, filename='count.csv')
        with open(count_file, 'w') as f:
            csv.writer(f).writerows([
                ['key', 'value'],
                ['lambdas', count],
                ['skipped_files', skipped],
                ['files', len(files)],
            ])

    @staticmethod
    def handle_file(language, repository_name, _file):
        """return (count, skipped)"""
        path = _file[0]
        count = int(_file[1])
        if count != -1:
            return count, 0, []
        try:
            count, sample = counters.count_lambdas(language, repository_name, path)
            if sample:
                sample = [(path, s[0], s[1]) for s in sample]
            return count, 0, sample
        except counters.SkipFile:
            return 0, 1, []

    @staticmethod
    def make_repo_summary(selector):
        parts = selector.split('/')
        if len(parts) != 3:
            raise Exception('bad selector')
        language = parts[0]
        owner = parts[1]
        repository = parts[2]
        data_file = get_data_file(language, owner, repository)
        with open(data_file, 'r') as f:
            f.readline()
            commits = list(csv.reader(f))
        summary_file = get_data_file(language, owner, repository, filename='summary.csv')
        full_sample_file = get_data_file(language, owner, repository, filename='full_sample.txt')
        with open(summary_file, 'w') as sf:
            with open(full_sample_file, 'w') as fsf:
                w = csv.writer(sf)
                w.writerow(['date', 'lambdas', 'skipped', 'files'])
                for date, commit in commits:
                    data_file = get_data_file(language, owner, repository, commit, filename='count.csv')
                    with open(data_file, 'r') as f:
                        f.readline()
                        rows = list(csv.reader(f))
                    counts = {r[0]: r[1] for r in rows}
                    w.writerow([date, counts['lambdas'], counts['skipped_files'], counts['files']])
                    sample_file = get_data_file(language, owner, repository, commit, filename='sample.txt')
                    with open(sample_file, 'r') as f:
                        fsf.write(f.read())

    @staticmethod
    def merge_all_data():
        summary_file = get_data_file(filename='summary.csv')
        with open(summary_file, 'w') as sf:
            w = csv.writer(sf)
            w.writerow(['language', 'nameWithOwner', 'date', 'file_count', 'skipped_file_count', 'lambda_count'])
            for language in const.LANGUAGES:
                repositories = github_api.get_repositories(language, const.REPOSITORY_COUNT, get_data_file(language))
                for repository in repositories:
                    owner = repository[1]
                    name = repository[2]
                    repository_summary_file = get_data_file(language, owner, name, filename='summary.csv')
                    with open(repository_summary_file, 'r') as rsf:
                        reader = csv.DictReader(rsf)
                        for row in reader:
                            w.writerow([
                                language,
                                f'{owner}/{name}',
                                row['date'],
                                row['files'],
                                row['skipped'],
                                row['lambdas'],
                            ])


def get_data_file(*args, filename='data.csv'):
    parts = [const.DATA_DIR, *args, '!', f'{filename}']
    path = '/'.join(parts)
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


if __name__ == '__main__':
    fire.Fire(Main)
