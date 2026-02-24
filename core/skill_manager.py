import os
from datetime import datetime


class SkillManager:
    """
    Trinity Skill Manager
    Automatically discovers and loads all skills
    Generates system prompt for Trinity
    Routes tool calls to correct skill
    Add a new skill file and it works automatically
    No configuration needed
    """

    def __init__(self, gh_token=None, brain_file="memory/trinity_brain.json"):
        self.gh_token = gh_token
        self.brain_file = brain_file
        self.skills = {}
        self.pending_changes = {}
        self.load_all_skills()

    def load_all_skills(self):
        """
        Load all skills automatically
        Order matters - some skills depend on others
        """
        print("Loading Trinity skills...")

        from skills.memory_skill import MemorySkill
        memory_skill = MemorySkill(
            brain_file=self.brain_file
        )
        self.skills['memory'] = memory_skill
        print("  Memory skill loaded")

        from skills.github_skill import GitHubSkill
        github_skill = GitHubSkill(
            gh_token=self.gh_token
        )
        self.skills['github'] = github_skill
        print("  GitHub skill loaded")

        from skills.web_skill import WebSkill
        web_skill = WebSkill()
        self.skills['web'] = web_skill
        print("  Web skill loaded")

        from skills.search_skill import SearchSkill
        search_skill = SearchSkill()
        self.skills['search'] = search_skill
        print("  Search skill loaded")

        from skills.code_skill import CodeSkill
        code_skill = CodeSkill(
            github_skill=github_skill
        )
        self.skills['code'] = code_skill
        print("  Code skill loaded")

        from skills.business_skill import BusinessSkill
        business_skill = BusinessSkill(
            memory_skill=memory_skill
        )
        self.skills['business'] = business_skill
        print("  Business skill loaded")

        print(f"All {len(self.skills)} skills loaded!")

    def get_skill(self, skill_name):
        """Get a specific skill by name"""
        return self.skills.get(skill_name)

    def execute(self, skill_name, tool_name, params=None):
        """
        Execute any tool from any skill
        Trinity calls this for everything
        """
        if params is None:
            params = {}

        skill = self.skills.get(skill_name)
        if not skill:
            return {
                'success': False,
                'error': f"Skill {skill_name} not found",
                'available_skills': list(self.skills.keys())
            }

        try:
            result = skill.execute(tool_name, params)
            return result
        except Exception as e:
            return {
                'success': False,
                'error': f"Error executing {skill_name}.{tool_name}: {str(e)}"
            }

    def get_pending_changes(self):
        """Get all pending changes across all skills"""
        all_pending = {}

        github_skill = self.skills.get('github')
        if github_skill:
            pending = github_skill.get_pending_changes()
            all_pending.update(pending)

        return all_pending

    def commit_change(self, change_id):
        """Commit approved change"""
        github_skill = self.skills.get('github')
        if github_skill:
            return github_skill.commit_change(change_id)
        return False, "GitHub skill not available"

    def cancel_change(self, change_id):
        """Cancel pending change"""
        github_skill = self.skills.get('github')
        if github_skill:
            return github_skill.cancel_change(change_id)
        return False

    def get_trinity_prompt(self):
        """
        Auto generate skills section of Trinity prompt
        Reads all loaded skills and their tools
        Trinity knows exactly what it can do
        """
        prompt = "SKILLS AND TOOLS AVAILABLE TO TRINITY:\n\n"

        for skill_name, skill in self.skills.items():
            prompt += f"SKILL: {skill.name.upper()}\n"
            prompt += f"Purpose: {skill.description}\n"
            prompt += "Tools:\n"

            tools = skill.get_tools()
            for tool in tools:
                approval = " [NEEDS YOUR APPROVAL]" \
                    if tool.get('needs_approval') else ""
                params = ", ".join(tool.get('params', []))
                prompt += f"  - {tool['name']}({params}){approval}\n"
                prompt += f"    {tool['description']}\n"

            prompt += "\n"

        prompt += """HOW TO USE SKILLS:
When David asks something, pick the right skill and tool.
For read operations: Execute immediately and return result.
For write operations: Always prepare first and show David preview.
David must say YES before any changes are committed.

TOOL CALL FORMAT:
When you need to use a tool, include in your response:
SKILL_CALL
skill: [skill_name]
tool: [tool_name]
params:
  key: value
  key: value
END_SKILL_CALL

Trinity will execute the tool and include result in response.

IMPORTANT RULES:
1. Always read file before updating it
2. Never replace full file when David asks to add one line
3. Use add_to_file when adding content to existing file
4. Use update_file only when replacing specific content
5. Always show preview before committing
6. Never commit without David saying YES
"""
        return prompt

    def get_github_context(self):
        """Get live GitHub context for briefings"""
        github_skill = self.skills.get('github')
        if not github_skill:
            return ""

        try:
            context = github_skill.get_all_repos_context()
            lines = ["LIVE GITHUB STATUS:"]

            for repo, data in context.items():
                lines.append(f"\n{repo}:")
                lines.append(
                    f"  Files: {data['total_files']}"
                )

                commits = data.get('recent_commits', [])
                if commits:
                    lines.append(
                        f"  Last commit: {commits[0]['message'][:50]}"
                    )

                workflows = data.get('recent_workflows', [])
                failed = [
                    w for w in workflows
                    if w.get('conclusion') == 'failure'
                ]
                if failed:
                    lines.append(
                        f"  FAILED workflows: {len(failed)}"
                    )

            return '\n'.join(lines)
        except Exception as e:
            return f"GitHub context error: {str(e)}"

    def get_health_summary(self):
        """Get overall system health"""
        results = {
            'checked_at': datetime.now().isoformat(),
            'skills_loaded': len(self.skills),
            'skill_status': {}
        }

        for skill_name, skill in self.skills.items():
            results['skill_status'][skill_name] = 'active'

        web_skill = self.skills.get('web')
        if web_skill:
            website = web_skill.execute(
                'check_website',
                {'url': 'https://trinity6.com'}
            )
            results['website'] = website
            results['website_live'] = website.get('is_live', False)

        memory_skill = self.skills.get('memory')
        if memory_skill:
            brain = memory_skill.read_brain()
            results['memory_active'] = brain.get('success', False)
            results['days_alive'] = brain.get('days_alive', 0)

        return results

    def get_business_summary(self):
        """Get business summary for briefings"""
        business_skill = self.skills.get('business')
        if not business_skill:
            return {}

        return business_skill.execute(
            'get_business_status', {}
        )

    def process_skill_call(self, response_text):
        """
        Parse and execute skill calls from Trinity response
        Trinity includes SKILL_CALL blocks in responses
        SkillManager executes them and returns results
        """
        if 'SKILL_CALL' not in response_text:
            return None, response_text

        try:
            lines = response_text.split('\n')
            skill_name = ''
            tool_name = ''
            params = {}
            in_skill_call = False
            in_params = False
            result_text = []

            i = 0
            while i < len(lines):
                line = lines[i]

                if line.strip() == 'SKILL_CALL':
                    in_skill_call = True
                    i += 1
                    continue

                if line.strip() == 'END_SKILL_CALL':
                    in_skill_call = False
                    in_params = False

                    result = self.execute(
                        skill_name, tool_name, params
                    )

                    result_text.append(
                        f"[Tool Result: {skill_name}.{tool_name}]"
                    )
                    result_text.append(str(result))

                    skill_name = ''
                    tool_name = ''
                    params = {}
                    i += 1
                    continue

                if in_skill_call:
                    if line.startswith('skill:'):
                        skill_name = line.replace(
                            'skill:', ''
                        ).strip()
                    elif line.startswith('tool:'):
                        tool_name = line.replace(
                            'tool:', ''
                        ).strip()
                    elif line.strip() == 'params:':
                        in_params = True
                    elif in_params and ':' in line:
                        parts = line.strip().split(':', 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            value = parts[1].strip()
                            try:
                                if value.isdigit():
                                    value = int(value)
                                elif value.replace(
                                    '.', ''
                                ).isdigit():
                                    value = float(value)
                            except:
                                pass
                            params[key] = value
                else:
                    result_text.append(line)

                i += 1

            return result_text, '\n'.join(result_text)

        except Exception as e:
            return None, response_text

    def update_david_seen(self):
        """Update when David was last seen"""
        memory_skill = self.skills.get('memory')
        if memory_skill:
            memory_skill.execute(
                'update_david',
                {
                    'key': 'last_seen',
                    'value': datetime.now().isoformat()
                }
            )

    def add_conversation(self, role, message):
        """Add to conversation history"""
        memory_skill = self.skills.get('memory')
        if memory_skill:
            brain = memory_skill.load_brain()

            if 'history' not in brain:
                brain['history'] = {}
            if 'conversations' not in brain['history']:
                brain['history']['conversations'] = []

            entry = {
                'timestamp': datetime.now().isoformat(),
                'role': role,
                'message': message
            }

            conversations = brain['history']['conversations']
            conversations.append(entry)

            if len(conversations) > 100:
                brain['history']['conversations'] = \
                    conversations[-100:]

            memory_skill.save_brain(brain)
