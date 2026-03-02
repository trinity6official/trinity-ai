import os
import importlib
from datetime import datetime


class SkillBuilderSkill:
    """
    Trinity Skill Builder
    Lets Trinity create new skill files automatically when it needs
    capabilities that do not exist yet.

    Workflow:
      1. Trinity identifies a gap ("I need a calendar skill")
      2. Trinity calls skill_builder.create_skill with a name + tool list
      3. SkillBuilder writes a scaffold to skills/<name>_skill.py
      4. Trinity (or David) implements the tool methods
      5. SkillManager auto-discovers the new file — no restart needed

    All write operations need David's approval before being used in
    production.  The scaffold is harmless boilerplate until implemented.
    """

    name = "skill_builder"
    description = (
        "Build new skill files automatically when Trinity needs "
        "capabilities that do not exist yet"
    )

    # ── code template ─────────────────────────────────────────────

    _TEMPLATE = '''\
from datetime import datetime


class {class_name}:
    """
    {description}
    Auto-scaffolded by Trinity SkillBuilder on {date}
    Implement each tool method marked TODO below.
    """

    name = "{skill_name}"
    description = "{description}"

    def __init__(self):
        pass

    def get_tools(self):
        return [
{tools_list}        ]

    def execute(self, tool_name, params):
        tool_map = {{
{tool_map}        }}
        fn = tool_map.get(tool_name)
        if not fn:
            return {{"success": False, "error": f"Unknown tool: {{tool_name}}"}}
        try:
            return fn(**params)
        except Exception as e:
            return {{"success": False, "error": str(e)}}

{tool_methods}'''

    # ── tools ─────────────────────────────────────────────────────

    def get_tools(self):
        return [
            {
                "name": "create_skill",
                "description": (
                    "Scaffold a new skill file with stub tool methods. "
                    "David must approve before the file is committed."
                ),
                "params": ["skill_name", "description", "tools"],
                "needs_approval": True,
            },
            {
                "name": "list_available_skills",
                "description": "List all skills currently in the skills/ folder",
                "params": [],
                "needs_approval": False,
            },
            {
                "name": "skill_exists",
                "description": "Check if a skill file already exists",
                "params": ["skill_name"],
                "needs_approval": False,
            },
            {
                "name": "get_skill_template",
                "description": "Return the raw template used to scaffold skills",
                "params": [],
                "needs_approval": False,
            },
        ]

    def execute(self, tool_name, params):
        tool_map = {
            "create_skill":        self.create_skill,
            "list_available_skills": self.list_available_skills,
            "skill_exists":        self.skill_exists,
            "get_skill_template":  self.get_skill_template,
        }
        fn = tool_map.get(tool_name)
        if not fn:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        try:
            return fn(**params)
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── tool implementations ──────────────────────────────────────

    def create_skill(self, skill_name, description, tools):
        """
        Write a scaffold skill file to skills/<skill_name>_skill.py

        skill_name  - snake_case name, e.g. "calendar"
        description - one-line description of what the skill does
        tools       - list of dicts:
                      [{"name": "get_events", "description": "...",
                        "params": ["date"], "needs_approval": False}]
        """
        if not skill_name or not skill_name.replace('_', '').isalpha():
            return {
                "success": False,
                "error": "skill_name must be letters and underscores only"
            }

        skill_file = f"skills/{skill_name}_skill.py"
        if os.path.exists(skill_file):
            return {
                "success": False,
                "error": (
                    f"{skill_file} already exists. "
                    "Delete it first or use github skill to update it."
                ),
            }

        if not tools:
            return {
                "success": False,
                "error": "Provide at least one tool definition"
            }

        class_name = (
            ''.join(w.capitalize() for w in skill_name.split('_'))
            + 'Skill'
        )

        tools_list_lines = []
        tool_map_lines = []
        tool_method_blocks = []

        for tool in tools:
            tname = tool.get("name", "")
            tdesc = tool.get("description", "")
            tparams = tool.get("params", [])
            needs_approval = tool.get("needs_approval", False)

            tools_list_lines.append(
                f'            {{'
                f'"name": "{tname}", '
                f'"description": "{tdesc}", '
                f'"params": {tparams}, '
                f'"needs_approval": {needs_approval}'
                f'}},'
            )
            tool_map_lines.append(
                f'            "{tname}": self.{tname},'
            )

            param_str = ", ".join(tparams)
            sig = f"self, {param_str}" if param_str else "self"
            method = (
                f"    def {tname}({sig}):\n"
                f'        """TODO: implement {tname} — {tdesc}"""\n'
                f'        return {{"success": False, "error": "Not implemented yet"}}\n'
            )
            tool_method_blocks.append(method)

        code = self._TEMPLATE.format(
            class_name=class_name,
            skill_name=skill_name,
            description=description,
            date=datetime.now().strftime("%Y-%m-%d"),
            tools_list="\n".join(tools_list_lines) + "\n",
            tool_map="\n".join(tool_map_lines) + "\n",
            tool_methods="\n".join(tool_method_blocks),
        )

        try:
            os.makedirs("skills", exist_ok=True)
            with open(skill_file, "w") as f:
                f.write(code)

            return {
                "success": True,
                "skill_name": skill_name,
                "file": skill_file,
                "class_name": class_name,
                "tools_created": [t.get("name") for t in tools],
                "next_steps": [
                    f"Open {skill_file} and implement each TODO method",
                    "SkillManager will auto-load it on next call — no restart needed",
                    "Test with: skill_manager.execute('"
                    + skill_name + "', '<tool_name>', {})",
                ],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_available_skills(self):
        """Return all skill names found in the skills/ folder."""
        if not os.path.exists("skills"):
            return {"success": False, "error": "skills/ directory not found"}

        files = sorted(
            f for f in os.listdir("skills")
            if f.endswith("_skill.py") and not f.startswith("__")
        )
        names = [f.replace("_skill.py", "") for f in files]

        return {
            "success": True,
            "available_skills": names,
            "total": len(names),
            "files": files,
        }

    def skill_exists(self, skill_name):
        """Check whether a skill file already exists."""
        skill_file = f"skills/{skill_name}_skill.py"
        exists = os.path.exists(skill_file)
        return {
            "success": True,
            "skill_name": skill_name,
            "exists": exists,
            "file": skill_file if exists else None,
        }

    def get_skill_template(self):
        """Return the raw scaffold template (for reference)."""
        return {
            "success": True,
            "template": self._TEMPLATE,
            "placeholders": [
                "class_name", "skill_name", "description",
                "date", "tools_list", "tool_map", "tool_methods",
            ],
        }
