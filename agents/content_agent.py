from datetime import datetime
from typing import Callable

from core.models import ChatMessage

class ContentAgent:
    """
    Trinity Content Agent
    Manages Trinity6 social media content drafts.
    Generation is local and safe; publishing is handled separately by
    permission-gated external-action tools.
    """
    
    def __init__(self, memory=None, llm=None, notifier: Callable[[str], object] | None = None):
        self.memory = memory
        self.llm = llm
        self.notifier = notifier
    
    # ==========================================
    # CONTENT GENERATION
    # ==========================================
    
    def generate_linkedin_post(self, topic=None):
        """Generate LinkedIn post using AI"""
        if not self.llm:
            return None
        
        if not topic:
            topic = self.get_todays_topic()
        
        prompt = f"""Write one LinkedIn post for Trinity6.

Topic: {topic}

Requirements:
- Under 200 words
- Strong opening line
- Professional but conversational
- End with one question
- 5 relevant hashtags
- No markdown stars or symbols
- Plain text only
- Ready to publish immediately"""
        
        try:
            messages = [
                ChatMessage("system", """You are Trinity6 content writer.
Trinity6 is an AI powered cybersecurity company.
Write content that builds thought leadership.
No markdown. No stars. Plain text only."""),
                ChatMessage("user", prompt),
            ]
            response = self.llm.invoke(messages)
            return response.content
            
        except Exception as e:
            print(f"Content generation error: {str(e)}")
            return None
    
    def generate_youtube_script(self, topic=None):
        """Generate YouTube Shorts script"""
        if not self.llm:
            return None
        
        if not topic:
            topic = self.get_todays_topic()
        
        prompt = f"""Write one YouTube Shorts script for Trinity6.

Topic: {topic}

Requirements:
- Maximum 60 seconds when read aloud
- Powerful hook in first 3 seconds
- Visual directions in brackets
- End with follow Trinity6 call to action
- Suggested title
- 5 hashtags
- No markdown stars or symbols
- Plain text only"""
        
        try:
            messages = [
                ChatMessage("system", """You are Trinity6 YouTube content creator.
Create viral short form cybersecurity content.
No markdown. No stars. Plain text only."""),
                ChatMessage("user", prompt),
            ]
            response = self.llm.invoke(messages)
            return response.content
            
        except Exception as e:
            print(f"Script generation error: {str(e)}")
            return None
    
    def get_todays_topic(self):
        """Pick todays content topic"""
        topics = [
            "Zero trust security architecture",
            "CIS benchmark compliance for SMBs",
            "Why 60 percent of SMBs fail after a cyberattack",
            "AI in cybersecurity threat detection",
            "What is GRC compliance and why it matters",
            "Network security basics every business needs",
            "The cost of a data breach in 2026",
            "How to prepare for SOC 2 certification",
            "NIST cybersecurity framework explained simply",
            "ISO 27001 vs SOC 2 which do you need",
            "Ransomware protection strategies for small business",
            "Why patch management is your first line of defense",
            "Multi factor authentication saves businesses",
            "Incident response planning for small teams",
            "Cloud security mistakes most companies make"
        ]
        
        day = datetime.now().day
        return topics[day % len(topics)]
    
    # ==========================================
    # CONTENT DELIVERY
    # ==========================================
    
    def deliver_content(self, content_type: str, content: str, notifier=None) -> bool:
        """Deliver a generated draft to an optional user-notification channel."""
        notify = notifier or self.notifier
        if notify is None:
            return False
        header = {
            "linkedin": "LinkedIn Post\n\n",
            "youtube": "YouTube Shorts Script\n\n",
        }.get(content_type, "Content\n\n")
        result = notify(header + content)
        return result is not False

    # ==========================================
    # CONTENT CALENDAR
    # ==========================================
    
    def get_content_calendar(self):
        """Get content plan for the week"""
        days = [
            'Monday',
            'Tuesday',
            'Wednesday',
            'Thursday',
            'Friday',
            'Saturday',
            'Sunday'
        ]
        
        themes = [
            'Cybersecurity threat awareness',
            'GRC compliance tips',
            'AI in security',
            'Technology trends',
            'Trinity6 product insights',
            'Weekend learning - security basics',
            'Weekly security roundup'
        ]
        
        calendar = []
        for i, day in enumerate(days):
            calendar.append({
                'day': day,
                'theme': themes[i],
                'platforms': ['LinkedIn', 'Twitter', 'Instagram'],
                'content_type': 'post'
            })
        
        return calendar
    
    def get_content_stats(self):
        """Get content performance summary"""
        if not self.memory:
            return {}
        
        logs = self.memory.get_recent_logs(7)
        
        content_logs = [
            log for log in logs
            if 'content' in str(log.get('entry', '')).lower()
            or 'post' in str(log.get('entry', '')).lower()
        ]
        
        return {
            'posts_this_week': len(content_logs),
            'platforms_active': [
                'LinkedIn',
                'Twitter',
                'Instagram'
            ],
            'next_post_topic': self.get_todays_topic(),
            'content_calendar': self.get_content_calendar()
        }
    
    def run_daily_content(self):
        """
        Generate daily content drafts. Optional delivery is only to David's
        configured notification channel; social publishing remains separate.
        """
        print("Trinity generating daily content...")
        
        topic = self.get_todays_topic()
        print(f"Today's topic: {topic}")
        
        linkedin_post = self.generate_linkedin_post(topic)
        if linkedin_post:
            self.deliver_content('linkedin', linkedin_post)
            
            if self.memory:
                self.memory.add_daily_log(
                    f"LinkedIn post generated about: {topic}"
                )
        
        youtube_script = self.generate_youtube_script(topic)
        if youtube_script:
            self.deliver_content('youtube', youtube_script)
            
            if self.memory:
                self.memory.add_daily_log(
                    f"YouTube script generated about: {topic}"
                )
        
        print("Daily content complete!")
        
        return {
            'topic': topic,
            'linkedin': linkedin_post is not None,
            'youtube': youtube_script is not None
        }
