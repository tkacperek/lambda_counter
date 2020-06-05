import csv
import datetime

import github
import gql
import gql.transport.requests

import constants as const

MAIN_QUERY = gql.gql('''
    query ($searchQuery: String!, $first: Int, $after: String) {
      search(type: REPOSITORY, query: $searchQuery, first: $first, after: $after) {
        pageInfo {
          endCursor
        }
        nodes {
          ... on Repository {
            nameWithOwner
            stargazers {
              totalCount
            }
            defaultBranchRef {
              target {
                ... on Commit {
                  oid
                  committedDate
                  history(first: 5) {
                    totalCount
                  }
                }
              }
            }
          }
        }
      }
    }
''')

INIT_COMMIT_QUERY = gql.gql('''
query ($name: String!, $owner: String!, $cursor: String!) {
  repository(name: $name, owner: $owner) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(last: 1, before: $cursor) {
            nodes {
              committedDate
            }
          }
        }
      }
    }
  }
}
''')


def get_repositories(language, count, data_file):
    try:
        with open(data_file, 'r') as f:
            f.readline()  # skip header
            return list(csv.reader(f))
    except FileNotFoundError:
        pass

    client = get_api_client()
    client_v3 = get_api_client(version=3)
    config = const.CONFIG[language]
    gh_language = config[const.KEYS.GITHUB_NAME]
    skip_repositories = config[const.KEYS.SKIP_REPOSITORIES]
    params = {
        'searchQuery': f'is:public language:{gh_language} stars:>100 sort:stars',
        'first': None,
        'after': None,
    }
    repositories = []
    missing_count = count

    while missing_count > 0:
        params.update(
            first=min(missing_count, const.GITHUB_API_CONFIG[const.KEYS.QUERY_SIZE_LIMIT]),
        )
        result = client.execute(MAIN_QUERY, variable_values=params)
        search_result = result['search']
        nodes = search_result['nodes']

        if not nodes:
            raise Exception('not enough repositories in GitHub')

        good_repositories = []
        for node in nodes:
            if node['nameWithOwner'] in skip_repositories:
                continue

            stars = node['stargazers']['totalCount']
            owner, name = node['nameWithOwner'].split('/')
            commit = node['defaultBranchRef']['target']

            max_date = datetime.date.fromisoformat(commit['committedDate'][:10])
            if max_date < const.MAX_COMMIT_DATE:
                continue

            oid = commit['oid']
            commit_count = commit['history']['totalCount']
            result = client.execute(INIT_COMMIT_QUERY, variable_values={
                'name': name,
                'owner': owner,
                'cursor': f'{oid} {commit_count}',
            })
            min_date = datetime.date.fromisoformat(
                result['repository']['defaultBranchRef']['target']['history']['nodes'][0]['committedDate'][:10],
            )
            if min_date > config[const.KEYS.START_DATE]:
                continue

            file_count = client_v3.search_code(f'repo:{owner}/{name} language:{gh_language}').totalCount
            if file_count < const.MIN_FILES_COUNT:
                continue

            good_repositories.append([stars, owner, name, min_date, max_date, file_count])

        repositories.extend(good_repositories)
        missing_count -= len(good_repositories)

        params.update(
            after=search_result['pageInfo']['endCursor'],
        )

    with open(data_file, 'w') as f:
        header = 'stars,owner,name,min_date,max_date,files\n'
        f.write(header)
        writer = csv.writer(f)
        writer.writerows(repositories)

    return repositories


def get_api_client(version=4):
    with open(const.GITHUB_API_CONFIG[const.KEYS.TOKEN_FILE], 'r') as f:
        token = f.read().strip()
    if version == 3:
        return github.Github(token)
    sample_transport = gql.transport.requests.RequestsHTTPTransport(
        url=const.GITHUB_API_CONFIG[const.KEYS.URL],
        headers={'Authorization': f'Bearer {token}'},
        retries=const.GITHUB_API_CONFIG[const.KEYS.RETRIES],
    )
    client = gql.Client(
        transport=sample_transport,
        fetch_schema_from_transport=True,
    )
    return client
