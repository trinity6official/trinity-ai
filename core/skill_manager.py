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
                 brain_file="trinity_brain.json"):
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

            elif skill_name == 'debug':
                from skills.debug_skill import DebugSkill
                github = self._skill_cache.get('github')
                skill = DebugSkill(github_skill=github)

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
        Pre load all skills if needed
        Usually not required due to lazy loading
        Only call this for morning briefing
        """
        for skill_name in [
            'memory', 'github', 'web',
            'search', 'code', 'business', 'debug'
        ]:
            self.get_skill(skill_name)
        print(f"All {len(self._skill_cache)} skills loaded.")

    # ==========================================
    # EXECUTE
    # ==========================================

    def execute(self, skill_name, tool_name, params=None):
        """
        Execute any tool from any skill
        Auto logs errors to debug skill
        Trinity can read error log and fix itself
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
                    'search', 'code', 'business', 'debug'
                ]
            }
    
        try:
            result = skill.execute(tool_name, params)
    
            if isinstance(result, dict) and \
               not result.get('success', True) and \
               result.get('error'):
                self.log_skill_error(
                    skill_name, tool_name,
                    result['error'], params
                )
    
            return result
    
        except Exception as e:
            error_msg = str(e)
            self.log_skill_error(
                skill_name, tool_name, error_msg, params
            )
            return {
                'success': False,
                'error': error_msg,
                'skill': skill_name,
                'tool': tool_name,
                'auto_debug': (
                    f"Error logged automatically. "
                    f"Trinity can use debug skill to "
                    f"analyze and fix this."
                )
            }

    def log_skill_error(self, skill_name, tool_name,
                     error, params):
        """Log error to debug skill automatically"""
        try:
            debug_skill = self.get_skill('debug')
            if debug_skill:
                debug_skill.log_error(
                    skill=skill_name,
                    method=tool_name,
                    error=error,
                    context=str(params)[:200]
                )
        except:
            pass


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

    def get_trinity_prompt(self):
        """
        Generate skills section of Trinity prompt
        Static list for fast response
        Trinity decides which skill to use
        based on what David asks naturally
        """
        return """SKILLS AVAILABLE TO TRINITY:
Trinity automatically picks the right skill.
David never needs to mention skills directly.

GITHUB SKILL
Purpose: Everything related to code and repositories
Tools:
  read_file(repo, path) - Read any file instantly
  list_files(repo, path) - See all files in repo
  get_commits(repo, path, count) - See commit history
  get_commit_details(repo, commit_sha) - What changed in a commit
  get_workflow_runs(repo, count) - Check GitHub Actions status
  get_repo_info(repo) - Repository information
  get_branches(repo) - List all branches
  get_issues(repo, state) - Get open or closed issues
  create_file(repo, path, content, reason) - Create new file [NEEDS APPROVAL]
  update_file(repo, path, content, reason) - Replace file content [NEEDS APPROVAL]
  add_to_file(repo, path, content, position, reason) - Add to existing file [NEEDS APPROVAL]
  delete_file(repo, path, reason) - Delete file [NEEDS APPROVAL]
  revert_file(repo, path, commit_sha) - Revert to old version [NEEDS APPROVAL]
  create_multiple_files(files, reason) - Create many files at once [NEEDS APPROVAL]

WEB SKILL
Purpose: Monitor websites and security
Tools:
  check_website(url) - Is site up and how fast
  check_ssl(domain) - SSL certificate valid and expiry
  check_domain_expiry(domain) - Domain registration expiry
  read_webpage(url) - Read content from any webpage
  check_all_trinity6() - Full health check of trinity6.com
  check_response_headers(url) - Security headers audit

MEMORY SKILL
Purpose: Read and write Trinity brain and history
Tools:
  read_brain() - Full Trinity memory
  read_section(section) - Specific brain section
  search_history(query, days) - Search conversation history
  get_recent_logs(days) - Recent activity logs
  get_active_alerts() - Current active alerts
  update_david(key, value) - Update David information
  update_company(key, value) - Update company data
  add_client(name, company, status, notes) - Add to pipeline
  update_revenue(amount, source) - Record revenue
  log_decision(decision, outcome) - Log what Trinity decided
  learn(category, insight) - Record what Trinity learned
  add_log(entry) - Add daily log entry
  update_wellbeing(score, note) - Update David wellbeing

SEARCH SKILL
Purpose: Research news clients and market
Tools:
  search_cybersecurity_news() - Latest security news
  search_cis_updates() - CIS benchmark updates
  find_potential_clients(location, industry) - Find prospects
  research_competitor(competitor_name) - Competitor analysis
  search_linkedin_prospects(role, location, industry) - LinkedIn strategy
  get_market_intelligence() - Market trends and opportunities

CODE SKILL
Purpose: Review and understand Trinity6 code
Tools:
  review_file(repo, path) - Complete code review
  find_bugs(repo, path) - Find potential bugs
  check_python_syntax(repo, path) - Syntax check
  analyze_imports(repo, path) - Dependencies analysis
  get_functions(repo, path) - List all functions and classes
  check_code_quality(repo, path) - Quality metrics
  find_todos(repo) - Find all TODO comments
  compare_files(repo1, path1, repo2, path2) - Compare two files
  audit_security_code(repo, path) - Security vulnerability check
  get_codebase_overview(repo) - Full repo overview

BUSINESS SKILL
Purpose: Track revenue clients and growth
Tools:
  get_business_status() - Full health status
  get_client_pipeline() - All clients and prospects
  add_prospect(name, company, contact, notes) - Add prospect
  update_prospect_status(company, new_status, notes) - Update pipeline
  record_revenue(amount, client, description) - Record payment
  get_weekly_priorities() - This weeks priorities
  generate_invoice_details(client_name, service, amount) - Invoice
  get_growth_metrics() - Growth trends and milestones
  plan_outreach(target_count) - Weekly outreach plan
  calculate_mrr() - Monthly recurring revenue

DEBUG SKILL
Purpose: Trinity detects and fixes its own bugs
Tools:
  log_error(skill, method, error, context)
  analyze_error(skill, method, error)
  read_skill_code(skill_name)
  propose_fix(skill_name, method_name, fix_description)
  get_error_history(limit)

WHEN TRINITY HITS AN ERROR:
1. Do not repeat the same failing call
2. Use debug.analyze_error to understand what went wrong
3. Use debug.read_skill_code to read the failing code
4. Use github.update_file to fix the code
5. Show David the fix for approval
6. After YES commit the fix
7. Try the original task again

Trinity should never hit the same error twice.

HOW TRINITY USES SKILLS:
1. David asks something naturally
2. Trinity identifies which skill and tool fits
3. Trinity executes the tool automatically
4. Trinity returns result in plain language
5. David never needs to mention skills

FOR WRITE OPERATIONS:
1. Trinity reads existing file first
2. Trinity prepares the change
3. Trinity shows David a preview
4. David says YES or NO
5. Trinity commits only after YES

CRITICAL RULES:
- Always read file before updating it
- Use add_to_file when David says add not replace
- Use update_file only when replacing specific content
- Never remove existing content unless David explicitly asks
- Never commit without David saying YES
- Show clear preview of every change before committing
- If unsure what David wants ask before doing anything"""

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
            Supports both formats:
    
            Format 1 (inline - what LLM actually outputs):
            SKILL_CALL: github.read_file
            repo: Trinity6
            path: README.md
    
            Format 2 (block - old format):
            SKILL_CALL
            skill: github
            tool: read_file
            params:
            repo: Trinity6
            path: README.md
            END_SKILL_CALL
            """
            if 'SKILL_CALL' not in response_text:
                return None, response_text
    
            try:
                lines = response_text.split('\n')
                result_text = []
                all_results = []
                i = 0
    
                while i < len(lines):
                    line = lines[i]
                    stripped = line.strip()
    
                    # ── Format 1: SKILL_CALL: skill.tool ──
                    if stripped.upper().startswith('SKILL_CALL:') or stripped.upper().startswith('SKILL_CALL :'):
                        # Parse "SKILL_CALL: github.read_file"
                        call_part = stripped.split(':', 1)[1].strip()
    
                        if '.' in call_part:
                            skill_name, tool_name = call_part.split('.', 1)
                            skill_name = skill_name.strip().lower()
                            tool_name = tool_name.strip()
                        else:
                            i += 1
                            continue
    
                        # Collect parameters from following lines
                        params = {}
                        i += 1
                        while i < len(lines):
                            param_line = lines[i].strip()
    
                            # Stop at empty line, next SKILL_CALL, or non-param line
                            if not param_line:
                                break
                            if param_line.upper().startswith('SKILL_CALL'):
                                break
                            if param_line.startswith('TRINITY_'):
                                break
    
                            # Parse "key: value"
                            if ':' in param_line:
                                key, value = param_line.split(':', 1)
                                key = key.strip()
                                value = value.strip()
    
                                # Skip if key looks like a sentence
                                if ' ' in key and len(key) > 20:
                                    break
    
                                # Type conversion
                                try:
                                    if value.isdigit():
                                        value = int(value)
                                    elif value.replace('.', '').isdigit():
                                        value = float(value)
                                except:
                                    pass
    
                                params[key] = value
                            else:
                                break
    
                            i += 1
    
                        # Execute the skill call
                        result = self.execute(skill_name, tool_name, params)
                        all_results.append(result)
                        result_text.append(f"[{skill_name}.{tool_name} result]")
                        result_text.append(str(result))
                        continue
    
                    # ── Format 2: Block format with END_SKILL_CALL ──
                    elif stripped == 'SKILL_CALL':
                        skill_name = ''
                        tool_name = ''
                        params = {}
                        in_params = False
                        i += 1
    
                        while i < len(lines):
                            block_line = lines[i].strip()
    
                            if block_line == 'END_SKILL_CALL':
                                result = self.execute(
                                    skill_name, tool_name, params
                                )
                                all_results.append(result)
                                result_text.append(
                                    f"[{skill_name}.{tool_name} result]"
                                )
                                result_text.append(str(result))
                                i += 1
                                break
    
                            if block_line.startswith('skill:'):
                                skill_name = block_line.replace(
                                    'skill:', ''
                                ).strip().lower()
                            elif block_line.startswith('tool:'):
                                tool_name = block_line.replace(
                                    'tool:', ''
                                ).strip()
                            elif block_line == 'params:':
                                in_params = True
                            elif in_params and ':' in block_line:
                                parts = block_line.split(':', 1)
                                if len(parts) == 2:
                                    key = parts[0].strip()
                                    value = parts[1].strip()
                                    try:
                                        if value.isdigit():
                                            value = int(value)
                                        elif value.replace('.', '').isdigit():
                                            value = float(value)
                                    except:
                                        pass
                                    params[key] = value
    
                            i += 1
                        continue
    
                    else:
                        result_text.append(line)
    
                    i += 1
    
                if all_results:
                    return all_results, '\n'.join(result_text)
                return None, response_text
    
            except Exception as e:
                print(f"[SKILL_MANAGER] Error parsing skill call: {e}")
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
