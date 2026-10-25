"""把 ECDICT 释义拆成普通释义和专业领域释义。"""

import re
from dataclasses import dataclass


DOMAIN_PREFIX = re.compile(r"^\s*[\[【]\s*([^\]】]+?)\s*[\]】]\s*(.*)$")


@dataclass(frozen=True)
class DomainMeaning:
    domain: str
    text: str


@dataclass(frozen=True)
class MeaningSections:
    general: tuple[str, ...]
    specialized: tuple[DomainMeaning, ...]


def parse_meanings(translation: str) -> MeaningSections:
    """拆分普通释义和 [医]、[计] 等专业领域释义。

    示例：
        "n. 苹果, 家伙\\n[医] 苹果"
        -> general=("n. 苹果, 家伙",)
           specialized=(DomainMeaning("医", "苹果"),)
    """

    general: list[str] = []
    specialized: list[DomainMeaning] = []
    lines = translation.replace("\\n", "\n").splitlines()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        matched = DOMAIN_PREFIX.match(line)
        if matched:
            domain, meaning = matched.groups()
            if meaning.strip():
                specialized.append(
                    DomainMeaning(domain=domain.strip(), text=meaning.strip())
                )
        else:
            general.append(line)

    return MeaningSections(
        general=tuple(general),
        specialized=tuple(specialized),
    )
