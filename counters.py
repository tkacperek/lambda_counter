import random
import re
import subprocess
import warnings

import esprima
import esprima.error_handler

import constants as const
from constants import CPP_SAMPLE_PROBABILITY, CPP_SAMPLE_CONTEXT_MARGIN


def count_lambdas(language, repository_name, path):
    if language == const.CPP_LANG:
        return count_lambdas_in_cpp(repository_name, path)
    elif language == const.JAVA_LANG:
        return count_lambdas_in_java(repository_name, path)
    elif language == const.JS_LANG:
        return count_lambdas_in_js(repository_name, path)
    else:
        raise Exception('bad language')


class SkipFile(Exception):
    pass


def count_lambdas_in_java(repository_name, path):
    full_path = f'{const.REPOSITORIES_DIR}/{repository_name}/{path}'
    cmd = f'java -jar java_counter/target/java_counter-1-shaded.jar {full_path}'
    try:
        result = subprocess.run(
            cmd.split(),
            capture_output=True,
            encoding='utf-8',
            check=True,
        )
    except subprocess.CalledProcessError:
        raise SkipFile
    return int(result.stdout), []


def count_lambdas_in_js(repository_name, path):
    full_path = f'{const.REPOSITORIES_DIR}/{repository_name}/{path}'
    warnings.simplefilter(action='ignore', category=FutureWarning)
    counter = JsCounter()
    try:
        try:
            with open(full_path, 'r') as f:
                esprima.parseModule(f.read(), delegate=counter)
        except esprima.error_handler.Error:
            counter.reset()
            cmd = f'flow-remove-types {full_path}'
            result = subprocess.run(
                cmd.split(),
                capture_output=True,
                encoding='utf-8',
                check=True,
            )
            esprima.parseModule(result.stdout, delegate=counter)
    except (esprima.error_handler.Error, UnicodeDecodeError, RecursionError):
        raise SkipFile
    return counter.count, []


class JsCounter:
    def __init__(self):
        self.count = 0

    def __call__(self, node, meta):
        if node.type == 'ArrowFunctionExpression':
            self.count += 1

    def reset(self):
        self.count = 0


def count_lambdas_in_cpp(repository_name, path):
    full_path = f'{const.REPOSITORIES_DIR}/{repository_name}/{path}'
    try:
        with open(full_path, 'r') as f:
            content = f.read()
    except UnicodeDecodeError:
        raise SkipFile
    original_content = content
    content = preprocess(content)

    lambda_re = LambdaRegex().compile()
    count = 0
    sample = []
    try:
        for bc in BracketsIterator(content):
            for match in lambda_re.finditer(bc):
                count += 1
                if random.random() < CPP_SAMPLE_PROBABILITY:
                    position = int(match.group(1))
                    sample.append((position, get_original_code(position, original_content)))
    except InvalidFinalContent:
        raise SkipFile
    return count, sample


def get_original_code(position, original_content):
    newline_count = 0
    pos = position
    while newline_count != CPP_SAMPLE_CONTEXT_MARGIN + 1 and pos != -1:
        pos = original_content.rfind('\n', 0, pos - 1)
        newline_count += 1
    start_pos = pos + 1

    newline_count = 0
    pos = position
    while newline_count != CPP_SAMPLE_CONTEXT_MARGIN + 1 and pos != -1:
        pos = original_content.find('\n', pos + 1)
        newline_count += 1
    end_pos = pos

    return original_content[start_pos:end_pos]


def preprocess(content):
    content = re.sub(r'\[(?!\')', lambda match: f'[<{match.start()}>', content)  # annotate lambda candidates positions

    content = content.replace('\\\n', '')  # join broken lines

    content = re.sub(r'\'\\?.\'', '\'\'', content)  # clear chars
    content = re.sub(r'"(?:[^\\\"\n]|(?:\\.))*"', '""', content)  # clear string contents

    content = re.sub(r'(?:(?<=^)|(?<=\n))#.*', '', content)  # remove directives
    content = re.sub(r'//.*', '', content)  # remove short comments

    content = content.replace('\n', ' ')  # join lines
    content = re.sub(r'/\*.*?\*/', '', content)  # remove long comments

    content = re.sub(r'\s+', ' ', content)  # simplify whitespaces
    return content


class InvalidFinalContent(Exception):
    pass


class BracketsIterator:
    BRACKETS = [('{', '}'), (r'\[', r'\]'), (r'\(', r'\)')]
    ALL_BS = ''.join(b for bs in BRACKETS for b in bs)

    def __init__(self, content):
        self.content = content
        self.previous_content = None
        self.leaf_cutter = self.compile_leaf_cutter()
        self.cuts = None

    def __iter__(self):
        self.add_root()
        self.clear_leaves()
        while self.previous_content != self.content:
            self.previous_content = self.content
            self.cut_leaves()
            yield from self.cuts
        if self.content != f'{self.BRACKETS[0][0]}{self.BRACKETS[0][1]}':
            raise InvalidFinalContent(self.content)

    def add_root(self):
        self.content = rf'{self.BRACKETS[0][0]}{self.content}{self.BRACKETS[0][1]}'

    def clear_leaves(self):
        for left, right in self.BRACKETS:
            if left != r'\[':
                self.content = re.sub(rf'({left})[^{self.ALL_BS}]+({right})', r'\g<1>\g<2>', self.content)
            else:
                self.content = re.sub(rf'\[<(\d+)>[^{self.ALL_BS}]*]', r'[\g<1>]', self.content)

    def compile_leaf_cutter(self):
        notallbs = fr'[^{self.ALL_BS}]'
        inner = r'(?:(?:{})|(?:\(\))|(?:\[\d+]))'
        mid = fr'((?:{notallbs}*{inner})+{notallbs}*)'
        pattern = fr'(?:({{){mid}(}}))|(?:(\(){mid}(\)))|(?:(\[)<(\d+)>{mid}(]))'
        return re.compile(pattern)

    def cut_leaves(self):
        self.cuts = []
        self.content = self.leaf_cutter.sub(self.sub_handler, self.content)

    def sub_handler(self, match_obj):
        content = match_obj.group(2) or match_obj.group(5) or match_obj.group(9)
        content = re.sub(r'operator\s*\[\d+]', 'operator', content)  # disarm operator[]
        self.cuts.append(content)

        left = match_obj.group(1) or match_obj.group(4) or match_obj.group(7)
        right = match_obj.group(3) or match_obj.group(6) or match_obj.group(10)
        position = match_obj.group(8) or ''
        return f'{left}{position}{right}'


class RE:
    @staticmethod
    def group(r):
        return rf'(?:{r})'

    @staticmethod
    def optional(r):
        gr = RE.group(r)
        return rf'{gr}?'

    @staticmethod
    def join(*rs):
        return r'\s?'.join(rs)

    @staticmethod
    def alternative(*rs):
        return r'|'.join(map(RE.group, rs))

    @staticmethod
    def many(r):
        gr = RE.group(r)
        return rf'{gr}*'


class LambdaRegex(RE):
    def compile(self):
        return re.compile(str(self))

    def __str__(self):
        return self.lambda_expression()

    def lambda_expression(self):
        return self.join(
            self.lambda_introducer(),
            self.optional(self.lambda_declarator()),
            self.compound_statement(),
        )

    @staticmethod
    def compound_statement():
        return r'{}'

    @staticmethod
    def lambda_introducer():
        return r'\[(\d+)\]'

    def lambda_declarator(self):
        return self.alternative(
            self.lambda_declarator_1(),
            self.lambda_declarator_2(),
        )

    def lambda_declarator_1(self):
        return self.join(
            r'\(\)',
            self.optional(self.decl_specifier_seq()),
        )

    def lambda_declarator_2(self):
        return self.join(
            self.optional(self.noexcept_specifier()),
            self.optional(self.attribute_specifier_seq()),
            self.optional(self.trailing_return_type()),
        )

    @staticmethod
    def decl_specifier_seq():
        alt = RE.group(RE.alternative(
            r'mutable',
            r'constexpr',
        ))
        return rf'{alt}{{1,2}}'

    @staticmethod
    def noexcept_specifier():
        return RE.alternative(
            RE.join(
                r'noexcept',
                RE.optional(r'\(\)'),
            ),
            RE.join(r'throw', r'\(\)'),
        )

    def trailing_return_type(self):
        return RE.join(
            r'\-\>',
            self.type_id(),
        )

    @staticmethod
    def type_id():
        return r'[^;]*?'

    def attribute_specifier_seq(self):
        return RE.many(self.attribute_specifier())

    @staticmethod
    def attribute_specifier():
        return RE.alternative(
            r'\[\]',
            RE.join(r'alignas', r'\(\)'),
        )
