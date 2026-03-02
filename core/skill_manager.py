import os
from datetime import datetime


class SkillManager:
    """
    Trinity Skill Manager
    Automatically discovers and loads skills lazily
    Generates system prompt for Trinity
    Routes tool calls to correct skill
    Trinity decides which skill to use automatically
    No configuration needed
    """

    def __init__(self, gh_token=None,
                 brain_file="memory/trinity_brain.json"):
        self.gh_token = gh_token
        self.brain_file = brain_file
        self._skill_cache = {}
        print("Skill Manager ready. Skills load on demand.")

    # ==========================================
    # SKILL LOADING - Lazy
    # ==========================================

    def get_skill(self, skill_name):
        """Load skill only when first needed"""
        if skill_name in self._skill_cache:
            return self._skill_cache[skill_name]

        print(f"Loading {skill_name} skill...")

        try:
            if skill_name == 'memory':
                from skills.memory_skill import MemorySkill
                skill = MemorySkill(
                    brain_file=self.brain_file
                )

            elif skill_name == 'github':
                from skills.github_skill import GitHubSkill
                skill = GitHubSkill(
                    gh_token=self.gh_token
                )

            elif skill_name == 'web':
                from skills.web_skill import WebSkill
                skill = WebSkill()

            elif skill_name == 'search':
                from skills.search_skill import SearchSkill
                skill = SearchSkill()

            elif skill_name == 'code':
                from skills.code_skill import CodeSkill
                github = self.get_skill('github')
                skill = CodeSkill(github_skill=github)

            elif skill_name == 'business':
                from skills.business_skill import BusinessSkill
                memory = self.get_skill('memory')
                skill = BusinessSkill(memory_skill=memory)

            elif skill_name == 'calculator':
                from skills.calculator_skill import CalculatorSkill
                skill = CalculatorSkill()

            elif skill_name == 'debug':
                from skills.debug_skill import DebugSkill
                skill = DebugSkill(skill_manager=self)

            else:
                print(f"Unknown skill: {skill_name}")
                return None

            self._skill_cache[skill_name] = skill
            print(f"{skill_name} skill loaded.")
            return skill

        except Exception as e:
            print(f"Error loading {skill_name}: {str(e)}")
            return None

    def load_all_skills(self):
        """
        Pre-load all skills if needed.
        Usually not required due to lazy loading.
        Only call for morning briefing or full health check.
        """
        for skill_name in [
            'memory', 'github', 'web',
            'search', 'code', 'business',
            'calculator', 'debug',
        ]:
            self.get_skill(skill_name)
        print(f"All {len(self._skill_cache)} skills loaded.")

    # ==========================================
    # EXECUTE
    # ==========================================

    def execute(self, skill_name, tool_name, params=None):
        """
        Execute any tool from any skill
        Trinity calls this automatically
        based on what David asks
        """
        if params is None:
            params = {}

        skill = self.get_skill(skill_name)
        if not skill:
            return {
                'success': False,
                'error': f"Skill {skill_name} not found",
                'available_skills': [
                    'github', 'web', 'memory',
                    'search', 'code', 'business'
                ]
            }

        try:
            return skill.execute(tool_name, params)
        except Exception as e:
            return {
                'success': False,
                'error': f"Error in {skill_name}.{tool_name}: {str(e)}"
            }

    # ==========================================
    # PENDING CHANGES
    # ==========================================

    def get_pending_changes(self):
        """Get all pending changes across all skills"""
        github_skill = self._skill_cache.get('github')
        if github_skill:
            return github_skill.get_pending_changes()
        return {}

    def commit_change(self, change_id):
        """Commit approved change"""
        github_skill = self._skill_cache.get('github')
        if github_skill:
            return github_skill.commit_change(change_id)
        return False, "GitHub skill not available"

    def cancel_change(self, change_id):
        """Cancel pending change"""
        github_skill = self._skill_cache.get('github')
        if github_skill:
            return github_skill.cancel_change(change_id)
        return False

    # ==========================================
    # TRINITY PROMPT - Static for speed
    # ==========================================

    def get_trinity_prompt(self, query=None):
        """
        Generate the skills section of Trinity's system prompt.
        When a query is provided, only include the skills relevant to that query.
        This saves tokens and keeps the LLM focused.
        """
        # Detect which skills are relevant to this query
        relevant = self._detect_relevant_skills(query) if query else None

        # Full skill definitions
        skill_blocks = {
            'github': """GITHUB SKILL
Purpose: Read, write, and manage code repositories
Tools:
  read_file(repo, path) - Read any file
  list_files(repo, path) - List files in a directory
  get_commits(repo, path, count) - Commit history
  get_commit_details(repo, commit_sha) - What changed in a commit
  get_workflow_runs(repo, count) - GitHub Actions status
  get_repo_info(repo) - Repository info
  get_branches(repo) - All branches
  get_issues(repo, state) - Open or closed issues
  create_file(repo, path, content, reason) - Create file [NEEDS APPROVAL]
  update_file(repo, path, content, reason) - Replace file [NEEDS APPROVAL]
  add_to_file(repo, path, content, position, reason) - Add to file [NEEDS APPROVAL]
  delete_file(repo, path, reason) - Delete file [NEEDS APPROVAL]
  revert_file(repo, path, commit_sha) - Revert to old version [NEEDS APPROVAL]
  create_multiple_files(files, reason) - Create many files [NEEDS APPROVAL]""",

            'web': """WEB SKILL
Purpose: Monitor websites, SSL, and security headers
Tools:
  check_website(url) - Is site up, response time
  check_ssl(domain) - SSL certificate status and expiry
  check_domain_expiry(domain) - Domain registration expiry
  read_webpage(url) - Read content from any webpage
  check_all_trinity6() - Full trinity6.com health check
  check_response_headers(url) - Security headers audit""",

            'memory': """MEMORY SKILL
Purpose: Read and write Trinity's brain and history
Tools:
  read_brain() - Full Trinity memory
  read_section(section) - Specific brain section
  search_history(query, days) - Search conversation history
  get_recent_logs(days) - Recent activity logs
  get_active_alerts() - Active alerts
  update_david(key, value) - Update David info
  update_company(key, value) - Update company data
  add_client(name, company, status, notes) - Add to pipeline
  update_revenue(amount, source) - Record revenue
  log_decision(decision, outcome) - Log a decision
  learn(category, insight) - Record a learning
  add_log(entry) - Add daily log entry
  update_wellbeing(score, note) - David wellbeing score
  pin_memory(key, value) - Permanently store a critical fact (never forgotten)
  get_pinned() - Read all permanently stored facts""",

            'search': """SEARCH SKILL
Purpose: Real web search — no fake or hardcoded data
Tools:
  search_web(query, max_results) - DuckDuckGo search
  search_cybersecurity_news() - Live headlines from security sources
  search_cis_updates() - CIS benchmark current versions
  find_potential_clients(location, industry) - Prospect search
  research_competitor(competitor_name) - Live + baseline competitor data
  search_linkedin_prospects(role, location, industry) - LinkedIn strategy
  get_market_intelligence() - Live market intel search
  check_source(url) - Check URL accessibility and page title""",

            'code': """CODE SKILL
Purpose: Review, analyze, and audit Trinity6 code
Tools:
  review_file(repo, path) - Complete code review
  find_bugs(repo, path) - Find potential bugs
  check_python_syntax(repo, path) - Syntax check
  analyze_imports(repo, path) - Dependencies analysis
  get_functions(repo, path) - Functions and classes list
  check_code_quality(repo, path) - Quality metrics
  find_todos(repo) - Find all TODO comments
  compare_files(repo1, path1, repo2, path2) - Diff two files
  audit_security_code(repo, path) - Security vulnerability check
  get_codebase_overview(repo) - Full repo overview""",

            'business': """BUSINESS SKILL
Purpose: Track revenue, clients, and company growth
Tools:
  get_business_status() - Full health status
  get_client_pipeline() - All clients and prospects
  add_prospect(name, company, contact, notes) - Add prospect
  update_prospect_status(company, new_status, notes) - Update status
  record_revenue(amount, client, description) - Record payment
  get_weekly_priorities() - This week's priorities
  generate_invoice_details(client_name, service, amount) - Invoice
  get_growth_metrics() - Growth trends and milestones
  plan_outreach(target_count) - Weekly outreach plan
  calculate_mrr() - Monthly recurring revenue""",

            'calculator': """CALCULATOR SKILL
Purpose: Safe math — never guesses, always computes
Tools:
  calculate(expression) - Evaluate any math expression safely
  calculate_mrr(clients, price_per_client) - Monthly recurring revenue
  calculate_revenue_target(target_inr, price_per_client, months) - Clients needed
  calculate_growth_rate(current_value, previous_value) - Growth percentage
  convert_units(value, from_unit, to_unit) - Currency/data/time conversion""",

            'debug': """DEBUG SKILL
Purpose: Log errors, test skills, detect failure patterns
Tools:
  log_error(skill_name, tool_name, error_message, params) - Log an error
  analyze_error(error_message) - Classify error and suggest fix
  test_skill_method(skill_name, tool_name, test_params) - Actually execute and test a skill
  get_error_history(limit) - Recent error log
  get_error_patterns() - Detect recurring failures
  clear_errors() - Clear error log""",
        }

        if relevant is not None:
            selected = {k: skill_blocks[k] for k in relevant if k in skill_blocks}
        else:
            selected = skill_blocks

        blocks = "\n\n".join(selected.values())

        return f"""SKILLS AVAILABLE TO TRINITY:
Trinity automatically picks the right skill.
David never needs to mention skills directly.

{blocks}

HOW TRINITY USES SKILLS:
1. David asks something
2. Trinity picks the right skill and tool
3. Trinity executes it and returns a plain-language result

CRITICAL RULES:
- Use calculator.calculate for all arithmetic — never compute in your head
- Use search_web for any current events, news, or competitor info — never make up data
- Always read a file before updating it
- Use add_to_file when adding content, update_file only when replacing
- Never commit without David saying YES
- Show a clear preview of every change before committing
- If a skill returns an error, use debug.analyze_error to classify it
- Be honest: if you don't know something, say so and offer to search for it"""

    def _detect_relevant_skills(self, query):
        """
        Return a list of relevant skill names based on the query text.
        Always includes memory. Falls back to all skills for broad queries.
        """
        if not query:
            return None

        q = query.lower()
        skills = {'memory'}  # Always useful for context

        if any(w in q for w in [
            'github', 'file', 'commit', 'code', 'repo', 'branch',
            'workflow', 'pull request', 'issue', 'push', 'read file',
        ]):
            skills.add('github')

        if any(w in q for w in [
            'review', 'bug', 'syntax', 'import', 'function', 'class',
            'quality', 'todo', 'security audit', 'vulnerability',
            'analyze code', 'check code',
        ]):
            skills.add('code')
            skills.add('github')

        if any(w in q for w in [
            'website', 'ssl', 'domain', 'http', 'trinity6.com',
            'security headers', 'online', 'offline', 'check site',
        ]):
            skills.add('web')

        if any(w in q for w in [
            'news', 'search', 'competitor', 'client', 'prospect',
            'market', 'cis', 'linkedin', 'find', 'research',
            'latest', 'current', 'today', 'trend',
        ]):
            skills.add('search')

        if any(w in q for w in [
            'revenue', 'client', 'pipeline', 'business', 'invoice',
            'mrr', 'outreach', 'growth', 'milestone', 'priority',
        ]):
            skills.add('business')

        if any(w in q for w in [
            'calculate', 'math', 'convert', 'how much', 'how many',
            'percent', 'total', 'cost', 'price', 'inr', 'usd',
            'formula', 'equation', 'add up', 'multiply',
        ]):
            skills.add('calculator')

        if any(w in q for w in [
            'error', 'debug', 'test', 'broken', 'fix', 'failed',
            'not working', 'crash', 'exception', 'traceback',
        ]):
            skills.add('debug')

        # If 5+ skills triggered, just send everything — query is broad
        if len(skills) >= 5:
            return None

        return sorted(skills)

    # ==========================================
    # CONTEXT FOR BRIEFINGS
    # ==========================================

    def get_github_context(self):
        """Get live GitHub context for briefings"""
        try:
            github_skill = self.get_skill('github')
            if not github_skill:
                return ""

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
            'skills_loaded': len(self._skill_cache),
            'skill_status': {}
        }

        for skill_name in self._skill_cache:
            results['skill_status'][skill_name] = 'active'

        try:
            web_skill = self.get_skill('web')
            if web_skill:
                website = web_skill.execute(
                    'check_website',
                    {'url': 'https://trinity6.com'}
                )
                results['website'] = website
                results['website_live'] = website.get(
                    'is_live', False
                )
        except:
            results['website_live'] = False

        try:
            memory_skill = self.get_skill('memory')
            if memory_skill:
                brain = memory_skill.read_brain()
                results['memory_active'] = brain.get(
                    'success', False
                )
                results['days_alive'] = brain.get(
                    'days_alive', 0
                )
        except:
            results['memory_active'] = False

        return results

    def get_business_summary(self):
        """Get business summary for briefings"""
        try:
            business_skill = self.get_skill('business')
            if not business_skill:
                return {}
            return business_skill.execute(
                'get_business_status', {}
            )
        except:
            return {}

    # ==========================================
    # SKILL CALL PARSER
    # ==========================================

    def process_skill_call(self, response_text):
        """
        Parse and execute SKILL_CALL blocks
        Trinity includes these in responses
        SkillManager executes and returns results
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
                        f"[{skill_name}.{tool_name} result]"
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

    # ==========================================
    # CONVERSATION HELPERS
    # ==========================================

    def update_david_seen(self):
        """Update when David was last seen"""
        try:
            memory_skill = self.get_skill('memory')
            if memory_skill:
                memory_skill.execute(
                    'update_david',
                    {
                        'key': 'last_seen',
                        'value': datetime.now().isoformat()
                    }
                )
        except:
            pass

    def add_conversation(self, role, message):
        """Add to conversation history"""
        try:
            memory_skill = self.get_skill('memory')
            if not memory_skill:
                return

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
        except:
            pass
