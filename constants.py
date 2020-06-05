import datetime

CPP_LANG = 'cpp'
JAVA_LANG = 'java'
JS_LANG = 'js'

LANGUAGES = (CPP_LANG, JAVA_LANG, JS_LANG)

REPOSITORY_COUNT = 10
MIN_FILES_COUNT = 32

DATA_DIR = 'data'
REPOSITORIES_DIR = 'repositories'
GITHUB_URL = 'https://github.com'

MAX_COMMIT_DATE = datetime.date(2020, 6, 30)


class KEYS:
    URL = 'url'
    TOKEN_FILE = 'token_file'
    QUERY_SIZE_LIMIT = 'query_size_limit'
    RETRIES = 'retries'
    GITHUB_NAME = 'github_name'
    START_DATE = 'start_date'
    EXTENSIONS = 'extensions'
    SKIP_REPOSITORIES = 'skip_repositories'


CONFIG = {
    CPP_LANG: {
        KEYS.GITHUB_NAME: 'C++',
        KEYS.START_DATE: datetime.date(2011, 8, 12),
        KEYS.EXTENSIONS: ('cc', 'cpp', 'cxx', 'c++'),
        KEYS.SKIP_REPOSITORIES: ('ariya/phantomjs',),
    },
    JAVA_LANG: {
        KEYS.GITHUB_NAME: 'Java',
        KEYS.START_DATE: datetime.date(2014, 3, 18),
        KEYS.EXTENSIONS: ('java',),
        KEYS.SKIP_REPOSITORIES: ('elastic/elasticsearch',),
    },
    JS_LANG: {
        KEYS.GITHUB_NAME: 'JavaScript',
        KEYS.START_DATE: datetime.date(2015, 6, 1),
        KEYS.EXTENSIONS: ('js',),
        KEYS.SKIP_REPOSITORIES: (),
    },
}

GITHUB_API_CONFIG = {
    KEYS.TOKEN_FILE: 'config/token.txt',
    KEYS.URL: 'https://api.github.com/graphql',
    KEYS.QUERY_SIZE_LIMIT: 100,
    KEYS.RETRIES: 3,
}

CPP_SAMPLE_PROBABILITY = 0.001
CPP_SAMPLE_CONTEXT_MARGIN = 2
