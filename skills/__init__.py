"""
Trinity Skills Package
Auto discovered and loaded by SkillManager
Each skill gives Trinity new capabilities
Add a new skill file here and Trinity
automatically knows about it
No configuration needed
"""

from skills.github_skill import GitHubSkill
from skills.web_skill import WebSkill
from skills.memory_skill import MemorySkill
from skills.search_skill import SearchSkill
from skills.code_skill import CodeSkill
from skills.business_skill import BusinessSkill

ALL_SKILLS = [
    GitHubSkill,
    WebSkill,
    MemorySkill,
    SearchSkill,
    CodeSkill,
    BusinessSkill
]
