import asyncio
import logging
import pytz
import re
import json
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    ContextTypes, 
    filters
)

from test import HackRxSeleniumScraper


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
IST = pytz.timezone('Asia/Kolkata')
BOT_TOKEN = os.getenv('BOT_TOKEN')
HACKRX_USERNAME = os.getenv('HACKRX_USERNAME')
HACKRX_PASSWORD = os.getenv('HACKRX_PASSWORD')
DEFAULT_WEBHOOK_URL = "https://api.codebrothers.tech/api/v1/hackrx/run"
TASKS_FILE = 'scheduled_tasks.json'




@dataclass
class ScheduledTask:
    """Data class for scheduled tasks"""
    user_id: int
    task_id: str
    webhook_url: str
    notes: str
    scheduled_time: datetime
    status: str  # 'pending', 'running', 'completed', 'failed', 'cancelled'
    created_at: datetime
    results: Optional[Dict] = None


class TaskManager:
    """Manages task persistence and operations"""
    
    def __init__(self):
        self.tasks: Dict[str, ScheduledTask] = {}
        self.load_tasks()
    
    def save_tasks(self) -> None:
        """Save tasks to JSON file"""
        try:
            tasks_data = {}
            for task_id, task in self.tasks.items():
                task_dict = asdict(task)
                # Convert datetime objects to ISO strings
                task_dict['scheduled_time'] = task.scheduled_time.isoformat()
                task_dict['created_at'] = task.created_at.isoformat()
                tasks_data[task_id] = task_dict
            
            with open(TASKS_FILE, 'w') as f:
                json.dump(tasks_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving tasks: {e}")
    
    def load_tasks(self) -> None:
        """Load tasks from JSON file"""
        try:
            if os.path.exists(TASKS_FILE):
                with open(TASKS_FILE, 'r') as f:
                    tasks_data = json.load(f)
                
                for task_id, task_dict in tasks_data.items():
                    # Convert ISO strings back to datetime objects
                    task_dict['scheduled_time'] = datetime.fromisoformat(task_dict['scheduled_time'])
                    task_dict['created_at'] = datetime.fromisoformat(task_dict['created_at'])
                    self.tasks[task_id] = ScheduledTask(**task_dict)
                    
        except Exception as e:
            logger.error(f"Error loading tasks: {e}")
    
    def add_task(self, task: ScheduledTask) -> str:
        """Add a new task and save to file"""
        self.tasks[task.task_id] = task
        self.save_tasks()
        return task.task_id
    
    def get_user_tasks(self, user_id: int) -> List[ScheduledTask]:
        """Get all tasks for a specific user"""
        return [task for task in self.tasks.values() if task.user_id == user_id]
    
    def get_pending_tasks(self) -> List[ScheduledTask]:
        """Get all pending tasks"""
        return [task for task in self.tasks.values() if task.status == 'pending']
    
    def update_task_status(self, task_id: str, status: str, results: Optional[Dict] = None) -> None:
        """Update task status and results"""
        if task_id in self.tasks:
            self.tasks[task_id].status = status
            if results:
                self.tasks[task_id].results = results
            self.save_tasks()
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task"""
        if task_id in self.tasks and self.tasks[task_id].status == 'pending':
            self.tasks[task_id].status = 'cancelled'
            self.save_tasks()
            return True
        return False


class HackRxBot:
    """Main bot class handling all Telegram interactions"""
    
    def __init__(self):
        self.user_states: Dict[int, Dict] = {}
        self.scheduler_running = False
        self.event_loop = None
        self.task_manager = TaskManager()
    
    # State Management
    def get_user_state(self, user_id: int) -> Dict:
        """Get or create user state"""
        if user_id not in self.user_states:
            self.user_states[user_id] = {}
        return self.user_states[user_id]
    
    def clear_user_state(self, user_id: int) -> None:
        """Clear user state"""
        if user_id in self.user_states:
            del self.user_states[user_id]
    
    # Command Handlers
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        welcome_message = """🚀 **HackRx Automation Bot**

This bot will automatically submit your webhook URL to HackRx at your scheduled time and notify you when results are available!

**Commands:**
/start - Show this menu
/schedule - Schedule new submission
/mytasks - View scheduled submissions
/cancel - Cancel a submission

**Start by selecting /schedule**"""
        
        keyboard = [
            [InlineKeyboardButton("Schedule Submission", callback_data="schedule")],
            [InlineKeyboardButton("My Tasks", callback_data="mytasks")],
            [InlineKeyboardButton("Cancel Task", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline keyboard button callbacks"""
        query = update.callback_query
        await query.answer()
        
        handlers = {
            "schedule": self.start_scheduling,
            "mytasks": self.show_my_tasks,
            "cancel": self.start_cancellation
        }
        
        if query.data in handlers:
            await handlers[query.data](query, context)
        elif query.data.startswith("cancel_task_"):
            task_id = query.data.replace("cancel_task_", "")
            await self.cancel_task(query, context, task_id)
    
    # Scheduling Flow
    async def start_scheduling(self, query, context) -> None:
        """Start the scheduling process"""
        user_id = query.from_user.id
        self.clear_user_state(user_id)
        
        state = self.get_user_state(user_id)
        state['step'] = 'waiting_time'
        
        message = """**Schedule New Submission**

Please enter the time when you want to submit to HackRx.

**Supported formats:**
• `8:15 PM` or `8:15 AM`
• `20:15` (24-hour format)
• `Tomorrow 8:15 PM`
• `2024-01-15 8:15 PM`

**Examples:**
• `9:30 AM` - Today at 9:30 AM
• `Tomorrow 2:15 PM` - Tomorrow at 2:15 PM
• `2024-01-20 10:00 AM` - Specific date and time

All times are in IST (India Standard Time)."""
        
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def handle_time_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
        """Handle time input from user"""
        user_id = update.message.from_user.id
        state = self.get_user_state(user_id)
        
        try:
            scheduled_time = self.parse_time_input(text)
            state['scheduled_time'] = scheduled_time
            state['step'] = 'waiting_webhook'
            
            time_str = scheduled_time.strftime("%Y-%m-%d %I:%M %p IST")
            
            message = f"""**Time Set: {time_str}**

Now please enter your webhook URL.

**Default:** `{DEFAULT_WEBHOOK_URL}`

You can type 'default' to use the default webhook URL, or enter your custom URL."""
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except ValueError as e:
            error_msg = (f"Invalid time format: {str(e)}\n\n"
                        "Please try again with formats like:\n"
                        "• `8:15 PM`\n"
                        "• `Tomorrow 2:30 PM`\n"
                        "• `2024-01-20 10:00 AM`")
            await update.message.reply_text(error_msg)
    
    async def handle_webhook_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
        """Handle webhook URL input from user"""
        user_id = update.message.from_user.id
        state = self.get_user_state(user_id)
        
        if text.lower() == 'default':
            webhook_url = DEFAULT_WEBHOOK_URL
        else:
            # Basic URL validation
            if not (text.startswith('http://') or text.startswith('https://')):
                await update.message.reply_text("Please enter a valid URL starting with http:// or https://")
                return
            webhook_url = text
        
        state['webhook_url'] = webhook_url
        state['step'] = 'waiting_notes'
        
        message = """**Webhook URL Set**

Now please enter submission notes/description.

**Example:** "API endpoint test run #1" """
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def handle_notes_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
        """Handle notes input and create the task"""
        user_id = update.message.from_user.id
        state = self.get_user_state(user_id)
        
        # Create the task
        task_id = f"task_{user_id}_{int(time.time())}"
        task = ScheduledTask(
            user_id=user_id,
            task_id=task_id,
            webhook_url=state['webhook_url'],
            notes=text,
            scheduled_time=state['scheduled_time'],
            status='pending',
            created_at=datetime.now(IST)
        )
        
        self.task_manager.add_task(task)
        self.clear_user_state(user_id)
        
        # Format confirmation message
        time_str = task.scheduled_time.strftime("%Y-%m-%d %I:%M %p IST")
        now = datetime.now(IST)
        
        if task.scheduled_time > now:
            time_diff = task.scheduled_time - now
            hours, remainder = divmod(time_diff.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)
            remaining_str = f"{int(hours)}h {int(minutes)}m"
        else:
            remaining_str = "Overdue - will run soon"
        
        message = f"""🎉 **Task Scheduled Successfully!**

**Schedule Details:**
Time: {time_str}
 Webhook: {task.webhook_url}
Notes: {text}
Remaining: {remaining_str}

The bot will automatically:
1. Login to HackRx at the scheduled time
2. Submit your webhook URL with notes
3. Monitor for results and notify you
4. Send you the accuracy score and timing details

You can check your tasks anytime with /mytasks"""
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
        # Start scheduler if not running
        if not self.scheduler_running:
            self.start_scheduler(context.application)
    
    # Message Handler
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages based on user state"""
        user_id = update.message.from_user.id
        text = update.message.text.strip()
        state = self.get_user_state(user_id)
        
        if not state:
            await update.message.reply_text("Please use /start to begin.")
            return
        
        step_handlers = {
            'waiting_time': self.handle_time_input,
            'waiting_webhook': self.handle_webhook_input,
            'waiting_notes': self.handle_notes_input
        }
        
        step = state.get('step')
        if step in step_handlers:
            await step_handlers[step](update, context, text)
    
    # Task Management
    async def show_my_tasks(self, query, context) -> None:
        """Display user's tasks"""
        query = Update.callback_query

        if not query or not query.from_user:
            await context.bot.send_message(chat_id=Update.effective_chat.id, text="This command must be used via the buttons.")
        
        user_id = query.from_user.id
        
        tasks = self.task_manager.get_user_tasks(user_id)
        
        if not tasks:
            await query.edit_message_text("No scheduled tasks found.")
            return
        
        message = "**Your Scheduled Tasks**\n\n"
        
        status_emojis = {
            'pending': '',
            'running': '',
            'completed': '',
            'failed': '',
            'cancelled': ''
        }
        
        for task in sorted(tasks, key=lambda x: x.scheduled_time):
            emoji = status_emojis.get(task.status, '❓')
            time_str = task.scheduled_time.strftime("%Y-%m-%d %I:%M %p IST")
            
            message += f"{emoji} **{task.status.title()}**\n"
            message += f"Time: {time_str}\n"
            message += f"Notes: {task.notes}\n"
            
            if task.status == 'pending':
                now = datetime.now(IST)
                if task.scheduled_time > now:
                    time_diff = task.scheduled_time - now
                    hours, remainder = divmod(time_diff.total_seconds(), 3600)
                    minutes, _ = divmod(remainder, 60)
                    message += f"Remaining: {int(hours)}h {int(minutes)}m\n"
            
            if task.results:
                message += f"Results: {task.results.get('summary', 'Available')}\n"
            
            message += "\n"
        
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def start_cancellation(self, query, context) -> None:
        """Start task cancellation process"""
        user_id = query.from_user.id
        tasks = self.task_manager.get_user_tasks(user_id)
        pending_tasks = [t for t in tasks if t.status == 'pending']
        
        if not pending_tasks:
            await query.edit_message_text("No pending tasks to cancel.")
            return
        
        keyboard = []
        for task in pending_tasks:
            time_str = task.scheduled_time.strftime("%Y-%m-%d %I:%M %p")
            button_text = f"🕐 {time_str} - {task.notes[:20]}..."
            callback_data = f"cancel_task_{task.task_id}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Select a task to cancel:", reply_markup=reply_markup)
    
    async def cancel_task(self, query, context, task_id: str) -> None:
        """Cancel a specific task"""
        if self.task_manager.cancel_task(task_id):
            await query.edit_message_text("Task cancelled successfully!")
        else:
            await query.edit_message_text("Could not cancel task. It may have already started or completed.")
    
    # Time Parsing
    def parse_time_input(self, text: str) -> datetime:
        """Parse various time input formats"""
        text = text.strip().lower()
        now = datetime.now(IST)
        
        # Handle "tomorrow" prefix
        target_date = now.date()
        if text.startswith('tomorrow'):
            target_date = (now + timedelta(days=1)).date()
            text = text.replace('tomorrow', '').strip()
        
        # Handle explicit date
        date_match = re.match(r'(\d{4}-\d{1,2}-\d{1,2})\s+(.+)', text)
        if date_match:
            date_str, time_str = date_match.groups()
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            text = time_str
        
        # Parse time formats
        time_patterns = [
            (r'(\d{1,2}):(\d{2})\s*(am|pm)', self._parse_12hour),
            (r'(\d{1,2}):(\d{2})', self._parse_24hour),
        ]
        
        target_time = None
        for pattern, parser in time_patterns:
            match = re.match(pattern, text)
            if match:
                target_time = parser(match)
                break
        
        if not target_time:
            raise ValueError("Could not parse time format")
        
        # Combine date and time
        scheduled_dt = datetime.combine(target_date, target_time)
        scheduled_dt = IST.localize(scheduled_dt)
        
        # If the time is in the past and no explicit date was given, assume tomorrow
        if scheduled_dt <= now and date_match is None and not text.startswith('tomorrow'):
            scheduled_dt = scheduled_dt + timedelta(days=1)
        
        if scheduled_dt <= now:
            raise ValueError("Scheduled time must be in the future")
        
        return scheduled_dt
    
    def _parse_12hour(self, match) -> datetime.time:
        """Parse 12-hour format"""
        hour, minute, ampm = match.groups()
        hour = int(hour)
        minute = int(minute)
        
        if ampm == 'pm' and hour != 12:
            hour += 12
        elif ampm == 'am' and hour == 12:
            hour = 0
        
        return datetime.min.time().replace(hour=hour, minute=minute)
    
    def _parse_24hour(self, match) -> datetime.time:
        """Parse 24-hour format"""
        hour, minute = match.groups()
        return datetime.min.time().replace(hour=int(hour), minute=int(minute))
    
    # Task Scheduler
    def start_scheduler(self, application) -> None:
        """Start the background task scheduler"""
        if self.scheduler_running:
            return
        
        self.scheduler_running = True
        self.event_loop = asyncio.get_event_loop()
        
        def scheduler_thread():
            logger.info("Task scheduler started")
            while self.scheduler_running:
                try:
                    self.check_and_run_tasks(application)
                except Exception as e:
                    logger.error(f"Scheduler error: {e}")
                time.sleep(30)  # Check every 30 seconds
        
        thread = threading.Thread(target=scheduler_thread, daemon=True)
        thread.start()
    
    def check_and_run_tasks(self, application) -> None:
        """Check for tasks that need to run"""
        now = datetime.now(IST)
        pending_tasks = self.task_manager.get_pending_tasks()
        
        for task in pending_tasks:
            if task.scheduled_time <= now:
                logger.info(f"Running task {task.task_id} for user {task.user_id}")
                
                # Update task status to running
                self.task_manager.update_task_status(task.task_id, 'running')
                
                # Send notification that task is starting
                start_message = (f"🚀 **Task Started**\n\n"
                               f"Your HackRx submission is now running...\n"
                               f"📝 Notes: {task.notes}")
                self._schedule_notification(application, task.user_id, start_message)
                
                # Run the task in a separate thread
                thread = threading.Thread(
                    target=self.run_hackrx_task, 
                    args=(application, task),
                    daemon=True
                )
                thread.start()
    
    def _schedule_notification(self, application, user_id: int, message: str) -> None:
        """Schedule notification to be sent from the main event loop"""
        if self.event_loop and not self.event_loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self.send_task_notification(application, user_id, message),
                self.event_loop
            )
    
    async def send_task_notification(self, application, user_id: int, message: str) -> None:
        """Send notification to user"""
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to send notification to {user_id}: {e}")
            # Try without markdown if it fails
            try:
                plain_message = message.replace('*', '').replace('`', '').replace('_', '')
                await application.bot.send_message(chat_id=user_id, text=plain_message)
            except Exception as e2:
                logger.error(f"Failed to send plain notification to {user_id}: {e2}")
    
    # Task Execution
    def run_hackrx_task(self, application, task: ScheduledTask) -> None:
        """Run the HackRx submission task"""
        try:
            logger.info(f"Starting HackRx submission for task {task.task_id}")
            
            # Create scraper instance
            scraper = HackRxSeleniumScraper(
                username=HACKRX_USERNAME,
                password=HACKRX_PASSWORD,
                headless=True  # Fixed: Changed to True for automation
            )
            
            results = self.execute_hackrx_submission(scraper, task, application)
            
            if results['success']:
                self.task_manager.update_task_status(task.task_id, 'completed', results)
            else:
                self.task_manager.update_task_status(task.task_id, 'failed', results)
                
        except Exception as e:
            logger.error(f"Task execution error: {e}")
            error_results = {'success': False, 'error': str(e)}
            self.task_manager.update_task_status(task.task_id, 'failed', error_results)
            
            error_message = (f"**Task Failed**\n\n"
                           f"Notes: {task.notes}\n"
                           f"Error: {str(e)}")
            self._schedule_notification(application, task.user_id, error_message)
    
    def execute_hackrx_submission(self, scraper: HackRxSeleniumScraper, task: ScheduledTask, application) -> Dict:
        """Execute the HackRx submission with monitoring"""
        try:
            # Create WebDriver
            if not scraper.create_driver():
                return {"success": False, "error": "Failed to create WebDriver"}
            
            try:
                # Login
                if not scraper.login():
                    return {"success": False, "error": "Login failed"}
                
                # Submit webhook
                submission_result = scraper.submit_webhook(task.webhook_url, task.notes)
                
                if not submission_result["success"]:
                    return {"success": False, "error": f"Submission failed: {submission_result['error']}"}
                
                # Monitor results
                results = self.monitor_results_with_cooldown_detection(scraper, task, application)
                
                return {
                    "success": True,
                    "submission_result": submission_result,
                    "monitoring_results": results
                }
            
            finally:
                if scraper.driver:
                    scraper.driver.quit()
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def monitor_results_with_cooldown_detection(self, scraper: HackRxSeleniumScraper, task: ScheduledTask, application) -> Dict:
        """Enhanced monitoring with cooldown detection"""
        target_notes = task.notes
        max_initial_checks = 2  # Check twice for submission existence
        max_result_checks = 6000  # Wait up to 10 minutes for results
        
        logger.info(f"🔍 Starting monitoring for: '{target_notes}'")
        
        # Phase 1: Check if submission was accepted
        submission_found = False
        for initial_check in range(max_initial_checks):
            logger.info(f"Initial check #{initial_check + 1}/{max_initial_checks}")
            
            try:
                scraper.driver.get(scraper.submissions_all_url)
                scraper.wait_for_page_load()
                page_text = scraper.driver.page_source
                
                if target_notes.lower() in page_text.lower():
                    submission_found = True
                    logger.info("SUBMISSION FOUND! Moving to result monitoring...")
                    break
                else:
                    logger.info("⏳ Submission not found yet...")
                    if initial_check < max_initial_checks - 1:
                        time.sleep(10)
                        
            except Exception as e:
                logger.error(f" Initial monitoring error: {e}")
        
        # If submission not found, it's in cooldown
        if not submission_found:
            logger.info("Submission not found - sending cooldown notification")
            cooldown_message = f""" **Submission in Cooldown Mode**

📝 **Notes:** {target_notes}
🌐 **Webhook:** {task.webhook_url}

Your submission was processed but is currently in cooldown mode. This means:
• The submission was received by HackRx
• Results are not immediately available
• This is normal behavior during high traffic periods

The bot will continue monitoring, but you may need to check manually later.

**Submitted at:** {datetime.now(IST).strftime('%Y-%m-%d %I:%M %p IST')}"""
            
            self._schedule_notification(application, task.user_id, cooldown_message)
            
            return {
                "found": False,
                "cooldown": True,
                "message": "Submission in cooldown mode"
            }
        
        # Phase 2: Monitor for results
        logger.info("Monitoring for results with accuracy and scores...")
        
        for result_check in range(max_result_checks):
            logger.info(f"Result check #{result_check + 1}/{max_result_checks}")
            
            try:
                scraper.driver.get(scraper.submissions_all_url)
                scraper.wait_for_page_load()
                page_text = scraper.driver.page_source
                
                # Extract submission details
                details = scraper.extract_submission_details(page_text, target_notes)
                logger.info(f"Status: {details['status']}, Has Results: {details['has_results']}")
                
                
                # Check if we have substantial results
                if details["has_results"]:
                    logger.info("RESULTS WITH METRICS AVAILABLE!")
                    
                    success_message = self.format_detailed_success_message(task,  details)
                    self._schedule_notification(application, task.user_id, success_message)
                    
                    return {
                        "found": True,
                        "has_results": True,
                        "has_metrics": True,
                        "details": details,
                       
                    }
                
                elif details["has_error"]:
                    logger.info(" ERROR DETECTED!")
                    
                    error_message = f""" **Submission Error Detected**

📝 **Notes:** {target_notes}
🔍 **Error Details:** {details['details']}

🕐 **Detected at:** {datetime.now(IST).strftime('%Y-%m-%d %I:%M %p IST')}"""
                    
                    self._schedule_notification(application, task.user_id, error_message)
                    
                    return {
                        "found": True,
                        "has_results": False,
                        "has_error": True,
                        "details": details
                    }
                
                elif details["is_processing"]:
                    logger.info("Still processing...")
                    
                    # Send periodic updates every 10 checks
                    if result_check > 0 and result_check % 10 == 0:
                        processing_message = f"""**Still Processing**

 **Notes:** {target_notes}
 **Status:** {details['status']}

Your submission is still being evaluated. Please wait...

 **Update at:** {datetime.now(IST).strftime('%Y-%m-%d %I:%M %p IST')}"""
                        self._schedule_notification(application, task.user_id, processing_message)
                
                if result_check < max_result_checks - 1:
                    time.sleep(10)
                    
            except Exception as e:
                logger.error(f"Result monitoring error: {e}")
        
        # Timeout reache
        
        # Timeout reached
        logger.info("Result monitoring timeout reached")
        
        timeout_message = f"""**Monitoring Timeout**

 **Notes:** {target_notes}
The submission was found but results are taking longer than expected.
You can check manually on the HackRx platform.

 **Timeout at:** {datetime.now(IST).strftime('%Y-%m-%d %I:%M %p IST')}
        """
        
        self._schedule_notification(application, task.user_id, timeout_message)
        
        return {
            "found": True,
            "has_results": False,
            "timeout": True
        }

    async def send_task_notification(self, application, user_id: int, message: str):
        """Send notification to user"""
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to send notification to {user_id}: {e}")
            # Try without markdown if it fails
            try:
                await application.bot.send_message(
                    chat_id=user_id,
                    text=message.replace('*', '').replace('`', '').replace('_', '')
                )
            except Exception as e2:
                logger.error(f"Failed to send plain notification to {user_id}: {e2}")
    
    
    def format_success_message(self, task: ScheduledTask, results: Dict) -> str:
        """Format success notification message"""
        message = f"**Task Completed Successfully!**\n\n"
        message += f"**Notes:** {task.notes}\n"
        message += f" **Webhook:** {task.webhook_url}\n\n"
        
        monitoring = results.get('monitoring_results', {})
        
        if monitoring.get('found'):
            message += "**Results:**\n"
            
            if monitoring.get('accuracy'):
                message += f" Accuracy: {monitoring['accuracy']}\n"
            
            if monitoring.get('avg-response'):
                message += f"⏱ Response Time: {monitoring['avg_response']}\n"
            
            if monitoring.get('score'):
                message += f"Position: #{monitoring['score']}\n"
            
            if not any([monitoring.get('accuracy'), monitoring.get('timing'), monitoring.get('position')]):
                message += "✅ Submission processed successfully\n"
        else:
            message += "✅ **Submission completed** (results pending)\n"
        
        message += f"\n🕐 **Completed at:** {datetime.now(IST).strftime('%Y-%m-%d %I:%M %p IST')}"
        
        return message
    
    async def send_task_notification(self, application, user_id: int, message: str):
        """Send notification to user"""
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to send notification to user {user_id}: {e}")

def main():
    """Main function to run the bot"""
    bot = HackRxBot()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("schedule", bot.start_scheduling))
    application.add_handler(CommandHandler("mytasks", bot.show_my_tasks))
    application.add_handler(CommandHandler("cancel", bot.start_cancellation))
    application.add_handler(CallbackQueryHandler(bot.button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Start the bot
    logger.info("Starting HackRx Telegram Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()