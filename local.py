import calendar
import csv
import datetime
import itertools
import os
import pathlib
import shutil
import subprocess

import constants as const


def clone_repository(owner, name):
    path = f'{const.REPOSITORIES_DIR}/{name}'
    if os.path.exists(path):
        return
    url = f'{const.GITHUB_URL}/{owner}/{name}'
    cmd = f'git clone {url} {path}'
    subprocess.run(
        cmd.split(),
        capture_output=True,
        encoding='utf-8',
        check=True,
    )


def get_commits(language, repository_name, data_file):
    try:
        with open(data_file, 'r') as f:
            f.readline()  # skip header
            return list(csv.reader(f))
    except FileNotFoundError:
        pass

    repository_path = f'{const.REPOSITORIES_DIR}/{repository_name}'
    config = const.CONFIG[language]
    from_date = config[const.KEYS.START_DATE]
    to_date = const.MAX_COMMIT_DATE
    commits = []

    def get_first_commit_id_between_dates(after, before):
        """including after, excluding before"""
        cmd = 'git log --first-parent --format=format:"%h" ' \
              f'--after={after.isoformat()} --before={before.isoformat()} -1'
        result = subprocess.run(
            cmd.split(),
            cwd=repository_path,
            capture_output=True,
            encoding='utf-8',
            check=True,
        )
        return result.stdout.strip('"') or None

    for year in range(from_date.year, to_date.year + 1):
        date_from = datetime.date(year, 1, 1)
        date_to = datetime.date(year, 12, 31)
        if not get_first_commit_id_between_dates(date_from, date_to + datetime.timedelta(days=1)):
            continue
        from_month = 1
        to_month = 12
        if year == from_date.year:
            from_month = from_date.month
        if year == to_date.year:
            to_month = to_date.month
        for month in range(from_month, to_month + 1):
            to_day = calendar.monthrange(year, month)[1]
            date_from = datetime.date(year, month, 1)
            date_to = datetime.date(year, month, to_day)
            commit_id = get_first_commit_id_between_dates(date_from, date_to + datetime.timedelta(days=1))
            if commit_id:
                commits.append([date_from, commit_id])

    with open(data_file, 'w') as f:
        header = 'date,id\n'
        f.write(header)
        writer = csv.writer(f)
        writer.writerows(commits)

    return commits


def delete_repository(name):
    shutil.rmtree(f'{const.REPOSITORIES_DIR}/{name}', ignore_errors=True)


def checkout_commit(repository_name, commit):
    cmd = f'git checkout {commit}'
    subprocess.run(
        cmd.split(),
        cwd=f'{const.REPOSITORIES_DIR}/{repository_name}',
        capture_output=True,
        encoding='utf-8',
        check=True,
    )


def _get_diff_paths(root, prev_commit, commit):
    cmd = f'git diff --name-status --no-renames --diff-filter=AMD {prev_commit} {commit}'
    result = subprocess.run(
        cmd.split(),
        cwd=root,
        capture_output=True,
        encoding='utf-8',
        check=True,
    )
    return map(lambda x: x.split('\t'), filter(None, result.stdout.split('\n')))


def get_files(language, repository_name, commit, previous_commit, data_file_maker):
    data_file = data_file_maker(commit)
    try:
        with open(data_file, 'r') as f:
            f.readline()  # skip header
            return list(csv.reader(f))
    except FileNotFoundError:
        pass

    extensions = const.CONFIG[language][const.KEYS.EXTENSIONS]
    root = pathlib.Path(f'{const.REPOSITORIES_DIR}/{repository_name}')

    if not previous_commit:
        paths = itertools.chain(*[root.rglob(f'*.{e}') for e in extensions])
        paths = [str(pathlib.Path(*p.parts[2:])) for p in paths if not p.is_dir()]
        paths = sorted(paths)
        files = list(zip(paths, itertools.repeat(-1)))
    else:
        prev_data_file = data_file_maker(previous_commit)
        with open(prev_data_file, 'r') as f:
            f.readline()  # skip header
            files = {path: count for path, count in csv.reader(f)}
        diff_paths = _get_diff_paths(root, previous_commit, commit)
        for status, path in diff_paths:
            if path.split('.')[-1] not in extensions:
                continue
            elif status in ('A', 'M'):
                files[path] = -1
            elif status == 'D':
                del files[path]
            else:
                raise Exception('bad status')
        files = files.items()

    with open(data_file, 'w') as f:
        header = 'path,count\n'
        f.write(header)
        writer = csv.writer(f)
        writer.writerows(files)

    return files
