"""Read directed facts and priority clauses in the explicit delegation grammar."""
import re

from query_determinacy_delegation import ANSWER, GRANTOR, RECIPIENT, solve, structured_from_parser


F1_PATTERNS = (
    re.compile(rf'本件复核单的核发权仅有一笔委托：{RECIPIENT}从{GRANTOR}取得该权。'),
    re.compile(rf'本件复核单仅登记一条有效代签委托：委托方为{GRANTOR}，代签方为{RECIPIENT}。'),
    re.compile(rf'关于本件复核单，能替{GRANTOR}代签的只有{RECIPIENT}。这是唯一有效的授权委托。'),
)
CONCLUSION = r'(?P<answer>准入|不准入)'
OVERRIDES = r'(?P<overrides>R[12])'
R3_PATTERNS = (
    re.compile(rf'本条的生效条件是{RECIPIENT}取得{GRANTOR}授予的本件复核单核发权。'
               rf'条件满足时，本件判为{CONCLUSION}，本条取代{OVERRIDES}。'),
    re.compile(rf'适用本条须同时对上两个身份：授权方为{GRANTOR}，代签本件复核单的一方为{RECIPIENT}。'
               rf'身份符合时，本件判为{CONCLUSION}，该结论覆盖{OVERRIDES}。'),
    re.compile(rf'在替{GRANTOR}代签本件复核单的权力交给{RECIPIENT}时，'
               rf'用本条取代{OVERRIDES}，把本件判为{CONCLUSION}。'),
)


def fact_direction(text):
    """Return a directed grant only when the whole F1 record identifies one."""
    # Reuse the original F1 grammar and leave its frozen implementation intact.
    source = structured_from_parser({'F1': text, 'R3': ''})['grant']
    if source is None:
        for pattern in F1_PATTERNS:
            match = pattern.fullmatch(text)
            if match is not None:
                source = match.groupdict()
                break
    if source is None or source['grantor'] == source['recipient']:
        return None
    return source


def compare_grant(source, extracted):
    if source is None:
        return 'f1_unrecognized'
    if extracted is None:
        return 'model_grant_missing'
    if source == extracted:
        return 'confirmed'
    if extracted == {'grantor': source['recipient'], 'recipient': source['grantor']}:
        return 'roles_reversed'
    return 'different_roles'


def verify_fact(records, structure):
    """Keep confirmed grants and return an unresolved grant for other statuses."""
    source = fact_direction(records['F1'])
    status = compare_grant(source, structure['grant'])
    checked = structure if status == 'confirmed' else dict(structure, grant=None)
    return status, source, checked


def exception_from_source(text):
    """Read the required directed grant, decision, and overridden rule as one clause."""
    source = structured_from_parser({'F1': '', 'R3': text})['exception']
    if source is None:
        for pattern in R3_PATTERNS:
            match = pattern.fullmatch(text)
            if match is not None:
                source = dict(match.groupdict(), answer=ANSWER[match['answer']])
                break
    if source is None or source['grantor'] == source['recipient']:
        return None
    return source


def source_structure(records):
    return {'grant': fact_direction(records['F1']), 'exception': exception_from_source(records['R3'])}


def solve_from_sources(records):
    """Evaluate only clauses that the grammar can resolve from the original text."""
    return solve(records, source_structure(records))
