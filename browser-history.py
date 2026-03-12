import json
from datetime import datetime, timezone, date, timedelta
import html
from collections import defaultdict

INPUT_FILE = "Takeout/Chrome/History.json"
OUTPUT_FILE = "history.html"

def chrome_time_from_usec(usec):
    """Convert Google Takeout time_usec to YYYY-MM-DD HH:MM:SS local time."""
    # time_usec is microseconds since Unix epoch
    ts = usec / 1_000_000
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

def format_time_12hour(usec):
    """Convert time_usec to 12-hour format like '4:05 PM'."""
    if not usec:
        return ""
    ts = usec / 1_000_000
    dt = datetime.fromtimestamp(ts)
    # Use %I and strip leading zero for hour (cross-platform compatible)
    time_str = dt.strftime("%I:%M %p")
    # Remove leading zero from hour if present
    if time_str.startswith("0"):
        time_str = time_str[1:]
    return time_str

def get_date_label(entry_date):
    """Get a user-friendly date label with combined relative and absolute format."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    # Format the absolute date part
    absolute_date = entry_date.strftime("%A, %B %d, %Y")
    
    if entry_date == today:
        return f"Today - {absolute_date}"
    elif entry_date == yesterday:
        return f"Yesterday - {absolute_date}"
    else:
        return absolute_date

def format_duration(minutes):
    """Format duration in minutes as 'X hours Y minutes' or 'Y minutes'."""
    if minutes < 60:
        return f"{int(minutes)} min"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    if mins == 0:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{hours} hour{'s' if hours != 1 else ''} {mins} min"

def detect_sessions(entries, gap_threshold_minutes=30):
    """
    Detect browsing sessions from entries based on time gaps.
    Returns list of sessions, each with start_time, end_time, duration_minutes, visit_count.
    """
    if not entries:
        return []
    
    # Sort entries chronologically (oldest first)
    sorted_entries = sorted(entries, key=lambda x: x.get("time_usec", 0))
    
    sessions = []
    current_session = None
    
    for entry in sorted_entries:
        time_usec = entry.get("time_usec", None)
        if not time_usec:
            continue
        
        ts = time_usec / 1_000_000
        entry_time = datetime.fromtimestamp(ts)
        
        if current_session is None:
            # Start new session
            current_session = {
                'start_time': entry_time,
                'end_time': entry_time,
                'visit_count': 1
            }
        else:
            # Check if gap is too large (new session)
            time_gap = (entry_time - current_session['end_time']).total_seconds() / 60  # minutes
            
            if time_gap > gap_threshold_minutes:
                # Close current session and start new one
                duration = (current_session['end_time'] - current_session['start_time']).total_seconds() / 60
                sessions.append({
                    'start_time_usec': int(current_session['start_time'].timestamp() * 1_000_000),
                    'end_time_usec': int(current_session['end_time'].timestamp() * 1_000_000),
                    'duration_minutes': duration,
                    'visit_count': current_session['visit_count']
                })
                current_session = {
                    'start_time': entry_time,
                    'end_time': entry_time,
                    'visit_count': 1
                }
            else:
                # Continue current session
                current_session['end_time'] = entry_time
                current_session['visit_count'] += 1
    
    # Add final session
    if current_session:
        duration = (current_session['end_time'] - current_session['start_time']).total_seconds() / 60
        sessions.append({
            'start_time_usec': int(current_session['start_time'].timestamp() * 1_000_000),
            'end_time_usec': int(current_session['end_time'].timestamp() * 1_000_000),
            'duration_minutes': duration,
            'visit_count': current_session['visit_count']
        })
    
    return sessions

# Load JSON
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

entries = data.get("Browser History", [])

# Group entries by date and sort
entries_by_date = defaultdict(list)
for entry in entries:
    time_usec = entry.get("time_usec", None)
    if time_usec:
        ts = time_usec / 1_000_000
        dt = datetime.fromtimestamp(ts)
        entry_date = dt.date()
        entries_by_date[entry_date].append(entry)

# Sort entries within each date group (newest first) and sort date groups
for date_key in entries_by_date:
    entries_by_date[date_key].sort(key=lambda x: x.get("time_usec", 0), reverse=True)

# Sort date groups (newest first)
sorted_dates = sorted(entries_by_date.keys(), reverse=True)

# Prepare data structure for JavaScript
# Convert to a flat list with date grouping info for easier lazy loading
history_data = []
sessions_by_date = {}

for entry_date in sorted_dates:
    date_label = get_date_label(entry_date)
    
    # Detect sessions for this date
    day_entries = entries_by_date[entry_date]
    sessions = detect_sessions(day_entries, gap_threshold_minutes=30)
    sessions_by_date[entry_date.isoformat()] = sessions
    
    # Create a mapping of time_usec to session index for quick lookup
    session_map = {}
    for session_idx, session in enumerate(sessions):
        start_usec = session['start_time_usec']
        end_usec = session['end_time_usec']
        # Store session index for entries within this time range
        for entry in day_entries:
            entry_time_usec = entry.get("time_usec", None)
            if entry_time_usec and start_usec <= entry_time_usec <= end_usec:
                session_map[entry_time_usec] = session_idx
    
    for entry in day_entries:
        entry_time_usec = entry.get("time_usec", None)
        session_idx = session_map.get(entry_time_usec, None)
        history_data.append({
            'date': entry_date.isoformat(),
            'date_label': date_label,
            'title': entry.get("title", ""),
            'url': entry.get("url", ""),
            'favicon_url': entry.get("favicon_url", ""),
            'time_usec': entry_time_usec,
            'session_idx': session_idx  # Index of session this entry belongs to
        })

# Build HTML using list for efficient concatenation
html_parts = []
html_parts.append("""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Chrome History Export</title>
<style>
    :root {
        --bg-primary: #f8f9fa;
        --bg-secondary: #ffffff;
        --text-primary: #202124;
        --text-secondary: #5f6368;
        --link-color: #1a0dab;
        --border-color: #e8eaed;
        --entry-hover-bg: #f1f3f4;
        --search-border: #dadce0;
        --search-focus-border: #4285f4;
        --search-focus-shadow: rgba(66, 133, 244, 0.1);
        --toggle-bg: #e8eaed;
        --toggle-hover-bg: #dadce0;
    }

    [data-theme="dark"] {
        --bg-primary: #202124;
        --bg-secondary: #303134;
        --text-primary: #e8eaed;
        --text-secondary: #9aa0a6;
        --link-color: #8ab4f8;
        --border-color: #5f6368;
        --entry-hover-bg: #3c4043;
        --search-border: #5f6368;
        --search-focus-border: #8ab4f8;
        --search-focus-shadow: rgba(138, 180, 248, 0.1);
        --toggle-bg: #5f6368;
        --toggle-hover-bg: #80868b;
    }

    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        margin: 0;
        padding: 20px;
        background-color: var(--bg-primary);
        color: var(--text-primary);
        transition: background-color 0.3s, color 0.3s;
    }

    .container {
        max-width: 1000px;
        margin: 0 auto;
        background-color: var(--bg-secondary);
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12);
        padding: 24px;
        transition: background-color 0.3s;
    }

    .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0;
        position: sticky;
        top: 0;
        z-index: 20;
        background-color: var(--bg-secondary);
        padding: 20px 0;
        margin-top: -20px;
        padding-top: 20px;
        transition: padding 0.3s ease;
        border-bottom: 1px solid var(--border-color);
    }

    .header.compact {
        padding: 12px 0;
    }

    h1 {
        font-weight: 400;
        font-size: 28px;
        margin: 0;
        color: var(--text-primary);
        transition: font-size 0.3s ease;
    }

    h1.compact {
        font-size: 20px;
    }

    .header-right {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-shrink: 0;
    }

    .theme-toggle {
        background-color: var(--toggle-bg);
        border: none;
        border-radius: 20px;
        padding: 8px 16px;
        font-size: 14px;
        color: var(--text-primary);
        cursor: pointer;
        transition: background-color 0.2s;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .theme-toggle:hover {
        background-color: var(--toggle-hover-bg);
    }

    .theme-icon {
        width: 18px;
        height: 18px;
        fill: var(--text-primary);
        transition: fill 0.3s;
    }

    .search-box {
        width: 300px;
        padding: 10px 16px;
        font-size: 14px;
        border: 1px solid var(--search-border);
        border-radius: 24px;
        outline: none;
        transition: box-shadow 0.2s, border-color 0.2s;
        background-color: var(--bg-secondary);
        color: var(--text-primary);
    }

    .search-box:focus {
        border-color: var(--search-focus-border);
        box-shadow: 0 0 0 3px var(--search-focus-shadow);
    }

    .date-group {
        margin-bottom: 32px;
        position: relative;
    }

    .date-header {
        font-size: 16px;
        font-weight: 500;
        color: var(--text-primary);
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-top: 1px solid var(--border-color);
        border-bottom: 1px solid var(--border-color);
        display: flex;
        justify-content: space-between;
        align-items: center;
        position: sticky;
        top: 80px;
        background-color: var(--bg-secondary);
        z-index: 10;
        padding-top: 8px;
        margin-top: 0;
        gap: 16px;
        transition: top 0.3s ease;
    }

    body.compact-header .date-header {
        top: 64px;
    }
    
    .date-group {
        margin-top: 0;
    }

    .date-header-left {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-shrink: 0;
    }
    
    .date-header-middle {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-shrink: 0;
        margin-left: 16px;
    }

    .date-header-nav {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: nowrap;
        flex-shrink: 0;
        margin-left: auto;
    }

    .nav-button {
        background: none;
        border: 1px solid var(--border-color);
        color: var(--text-secondary);
        cursor: pointer;
        font-size: 11px;
        padding: 4px 8px;
        border-radius: 4px;
        transition: background-color 0.2s, border-color 0.2s, opacity 0.2s;
        white-space: nowrap;
        flex-shrink: 0;
        min-width: 44px;
        text-align: center;
    }

    .nav-button:hover:not(:disabled) {
        background-color: var(--entry-hover-bg);
        border-color: var(--text-secondary);
    }

    .nav-button:disabled {
        color: var(--text-secondary);
        opacity: 0.4;
        cursor: default;
    }

    .nav-button:disabled:hover {
        background-color: transparent;
        border-color: var(--border-color);
    }

    .date-picker-container {
        position: relative;
        display: inline-block;
        flex-shrink: 0;
    }

    .date-picker-trigger {
        background: none;
        border: 1px solid var(--border-color);
        color: var(--text-secondary);
        cursor: pointer;
        font-size: 11px;
        padding: 4px 8px;
        border-radius: 4px;
        transition: background-color 0.2s, border-color 0.2s;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .date-picker-trigger:hover {
        background-color: var(--entry-hover-bg);
        border-color: var(--text-secondary);
    }

    .date-picker-icon {
        width: 14px;
        height: 14px;
        fill: var(--text-secondary);
        transition: fill 0.2s;
    }

    .date-picker-trigger:hover .date-picker-icon {
        fill: var(--text-primary);
    }

    .date-picker {
        position: absolute;
        top: 100%;
        right: 0;
        margin-top: 4px;
        background-color: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        padding: 12px;
        min-width: 280px;
        z-index: 1000;
        display: none;
    }

    .date-picker.show {
        display: block;
    }

    .date-picker-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
        gap: 8px;
    }

    .date-picker-month-year {
        display: flex;
        gap: 8px;
        align-items: center;
    }

    .date-picker select {
        background-color: var(--bg-secondary);
        border: 1px solid var(--border-color);
        color: var(--text-primary);
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        cursor: pointer;
    }

    .date-picker-nav {
        background: none;
        border: none;
        color: var(--text-secondary);
        cursor: pointer;
        font-size: 16px;
        padding: 4px 8px;
        border-radius: 4px;
        transition: background-color 0.2s;
    }

    .date-picker-nav:hover {
        background-color: var(--entry-hover-bg);
    }

    .date-picker-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 4px;
    }

    .date-picker-day-header {
        text-align: center;
        font-size: 11px;
        font-weight: 500;
        color: var(--text-secondary);
        padding: 4px;
    }

    .date-picker-day {
        text-align: center;
        padding: 6px;
        font-size: 12px;
        border-radius: 4px;
        transition: background-color 0.2s;
        color: var(--text-secondary);
        cursor: default;
    }

    .date-picker-day.no-entries {
        color: var(--text-secondary);
        opacity: 0.5;
    }

    .date-picker-day.no-entries:hover {
        background-color: transparent;
    }

    .date-picker-day.has-entries {
        font-weight: 500;
        color: var(--link-color);
        cursor: pointer;
    }

    .date-picker-day.has-entries:hover {
        background-color: var(--entry-hover-bg);
    }

    .date-picker-day.other-month {
        color: var(--text-secondary);
        opacity: 0.5;
        cursor: default;
    }

    .date-picker-day.today {
        background-color: var(--link-color);
        color: white;
        font-weight: 600;
        cursor: pointer;
    }

    .date-picker-day.today:hover {
        background-color: var(--link-color);
        opacity: 0.9;
    }

    .date-picker-day.selected {
        background-color: var(--link-color);
        color: white;
        cursor: pointer;
    }

    .session-toggle {
        background: none;
        border: none;
        color: var(--text-secondary);
        cursor: pointer;
        font-size: 12px;
        padding: 4px 8px;
        border-radius: 4px;
        transition: background-color 0.2s;
        flex-shrink: 0;
        white-space: nowrap;
    }

    .session-toggle:hover {
        background-color: var(--entry-hover-bg);
    }

    .entry {
        display: flex;
        align-items: center;
        padding: 12px 0;
        transition: background-color 0.1s;
        border-radius: 4px;
        margin: 0 -8px;
        padding-left: 8px;
        padding-right: 8px;
        gap: 12px;
    }

    .entry:hover {
        background-color: var(--entry-hover-bg);
    }

    .entry-time {
        font-size: 12px;
        color: var(--text-secondary);
        white-space: nowrap;
        flex-shrink: 0;
        min-width: 70px;
    }

    .left {
        display: flex;
        align-items: center;
        gap: 12px;
        overflow: hidden;
        flex: 1;
        min-width: 0;
    }

    .favicon {
        width: 16px;
        height: 16px;
        flex-shrink: 0;
    }

    .entry-content {
        min-width: 0;
        flex: 1;
    }

    .title {
        font-size: 14px;
        margin-bottom: 4px;
        color: var(--link-color);
        text-decoration: none;
        display: block;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .title:hover {
        text-decoration: underline;
    }

    .url {
        font-size: 12px;
        color: var(--text-secondary);
        word-break: break-all;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .no-results {
        text-align: center;
        padding: 40px 20px;
        color: var(--text-secondary);
        font-size: 14px;
        display: none;
    }

    .loading-indicator {
        text-align: center;
        padding: 20px;
        color: var(--text-secondary);
        font-size: 14px;
        display: none;
    }

    .session-summary {
        background-color: var(--bg-secondary);
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
        border: 1px solid var(--border-color);
        position: sticky;
        top: 128px;
        z-index: 9;
        transition: clip-path 0.1s ease-out, opacity 0.15s ease-out, transform 0.15s ease-out, top 0.3s ease;
        overflow: hidden;
    }

    body.compact-header .session-summary {
        top: 112px;
    }
    
    .session-summary.closing {
        opacity: 0;
        transform: translateY(-8px);
        pointer-events: none;
    }
    
    .session-summary.clipped {
        /* clip-path will be set dynamically via JavaScript */
    }

    .session-summary-header {
        font-size: 14px;
        font-weight: 500;
        color: var(--text-primary);
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .session-list {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .session-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        background-color: var(--bg-secondary);
        border-radius: 4px;
        font-size: 13px;
    }

    .session-time {
        color: var(--text-primary);
        font-weight: 500;
    }

    .session-time-start,
    .session-time-end {
        cursor: pointer;
        text-decoration: underline;
        color: var(--link-color);
    }

    .session-time-start:hover,
    .session-time-end:hover {
        color: var(--link-color);
        opacity: 0.8;
    }

    .session-item {
        cursor: pointer;
        transition: background-color 0.2s;
    }

    .session-item:hover {
        background-color: var(--entry-hover-bg);
    }

    .session-duration {
        color: var(--text-secondary);
    }

    .session-visits {
        color: var(--text-secondary);
        font-size: 12px;
    }

    .session-stats {
        display: flex;
        gap: 16px;
        margin-top: 8px;
        font-size: 12px;
        color: var(--text-secondary);
    }
</style>
</head>
<body>
<div class="container">
<div class="header" id="topHeader">
<h1 id="pageTitle">Browser History</h1>
    <div class="header-right">
        <input type="text" class="search-box" id="searchInput" placeholder="Search history...">
        <button class="theme-toggle" id="themeToggle" aria-label="Toggle dark mode">
            <span id="themeIcon">
                <svg class="theme-icon" id="moonIcon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12.34 2.02C6.59 1.82 2 6.42 2 12c0 5.52 4.48 10 10 10 3.71 0 6.93-2.02 8.66-5.02-7.51-.88-13.1-7.25-8.32-14.98z"/>
                </svg>
                <svg class="theme-icon" id="sunIcon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" style="display: none;">
                    <circle cx="12" cy="12" r="5"/>
                    <line x1="12" y1="1" x2="12" y2="3"/>
                    <line x1="12" y1="21" x2="12" y2="23"/>
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                    <line x1="1" y1="12" x2="3" y2="12"/>
                    <line x1="21" y1="12" x2="23" y2="12"/>
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
                </svg>
            </span>
            <span id="themeText">Dark</span>
        </button>
    </div>
</div>
<div id="historyContainer"></div>
<div class="loading-indicator" id="loadingIndicator">Loading more...</div>
<div class="no-results" id="noResults">No results found</div>
</div>
<script>
    // Embedded history data
    const historyData = """)

# Embed JSON data
html_parts.append(json.dumps(history_data))
html_parts.append(""";
    const sessionsData = """)
html_parts.append(json.dumps(sessions_by_date))
html_parts.append(""";
    
    // Extract available dates for date picker highlighting
    const availableDates = new Set();
    historyData.forEach(entry => {
        if (entry.date) {
            availableDates.add(entry.date);
        }
    });
    
    // Calculate date range for limiting year/month selectors
    let minDate = null;
    let maxDate = null;
    availableDates.forEach(dateStr => {
        const date = new Date(dateStr + 'T00:00:00');
        if (!minDate || date < minDate) {
            minDate = date;
        }
        if (!maxDate || date > maxDate) {
            maxDate = date;
        }
    });
    
    const minYear = minDate ? minDate.getFullYear() : new Date().getFullYear();
    const minMonth = minDate ? minDate.getMonth() : 0;
    const maxYear = maxDate ? maxDate.getFullYear() : new Date().getFullYear();
    const maxMonth = maxDate ? maxDate.getMonth() : 11;
    
    // Configuration
    const INITIAL_LOAD = 150;  // Number of entries to load initially
    const CHUNK_SIZE = 50;     // Number of entries to load per chunk
    let renderedCount = 0;
    let isSearchMode = false;
    let filteredData = [];
    let currentData = historyData;
    let lastRenderedDate = null;  // Track last rendered date to prevent duplicate headers
    
    // DOM elements
    const searchInput = document.getElementById('searchInput');
    const historyContainer = document.getElementById('historyContainer');
    const noResults = document.getElementById('noResults');
    const loadingIndicator = document.getElementById('loadingIndicator');
    
    // Helper function to format time
    function formatTime12Hour(usec) {
        if (!usec) return "";
        const ts = usec / 1000000;
        const dt = new Date(ts * 1000);
        let hours = dt.getHours();
        const minutes = dt.getMinutes();
        const ampm = hours >= 12 ? 'PM' : 'AM';
        hours = hours % 12;
        hours = hours ? hours : 12;
        const minutesStr = minutes < 10 ? '0' + minutes : minutes;
        return hours + ':' + minutesStr + ' ' + ampm;
    }
    
    // Helper function to escape HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Helper function to format duration
    function formatDuration(minutes) {
        if (minutes < 60) {
            return Math.round(minutes) + ' min';
        }
        const hours = Math.floor(minutes / 60);
        const mins = Math.round(minutes % 60);
        if (mins === 0) {
            return hours + ' hour' + (hours !== 1 ? 's' : '');
        }
        return hours + ' hour' + (hours !== 1 ? 's' : '') + ' ' + mins + ' min';
    }
    
    // Render session summary for a date
    function renderSessionSummary(dateStr, groupId) {
        const sessions = sessionsData[dateStr] || [];
        if (sessions.length === 0) {
            return '';
        }
        
        const totalDuration = sessions.reduce((sum, s) => sum + s.duration_minutes, 0);
        const totalVisits = sessions.reduce((sum, s) => sum + s.visit_count, 0);
        
        let sessionsHtml = '<div class="session-summary" style="display: none;">';
        sessionsHtml += '<div class="session-summary-header">';
        sessionsHtml += '<span>' + sessions.length + ' session' + (sessions.length !== 1 ? 's' : '') + '</span>';
        sessionsHtml += '<div class="session-stats">';
        sessionsHtml += '<span>Total: ' + formatDuration(totalDuration) + '</span>';
        sessionsHtml += '<span>' + totalVisits + ' visit' + (totalVisits !== 1 ? 's' : '') + '</span>';
        sessionsHtml += '</div></div>';
        sessionsHtml += '<div class="session-list">';
        
        // Reverse sessions array to show most recent first
        const reversedSessions = [...sessions].reverse();
        reversedSessions.forEach((session, reversedIdx) => {
            // Calculate original session index (for navigation purposes)
            const originalSessionIdx = sessions.length - 1 - reversedIdx;
            const startTime = formatTime12Hour(session.start_time_usec);
            const endTime = formatTime12Hour(session.end_time_usec);
            const sessionId = groupId + '-session-' + originalSessionIdx;
            const dateStrEscaped = escapeHtml(dateStr);
            sessionsHtml += '<div class="session-item" data-date="' + dateStrEscaped + '" data-session-idx="' + originalSessionIdx + '" data-position="end">';
            sessionsHtml += '<div>';
            sessionsHtml += '<div class="session-time">';
            sessionsHtml += '<span class="session-time-start" data-date="' + dateStrEscaped + '" data-session-idx="' + originalSessionIdx + '" data-position="start">' + startTime + '</span>';
            sessionsHtml += ' - ';
            sessionsHtml += '<span class="session-time-end" data-date="' + dateStrEscaped + '" data-session-idx="' + originalSessionIdx + '" data-position="end">' + endTime + '</span>';
            sessionsHtml += '</div>';
            sessionsHtml += '<div class="session-duration">' + formatDuration(session.duration_minutes) + '</div>';
            sessionsHtml += '</div>';
            sessionsHtml += '<div class="session-visits">' + session.visit_count + ' page' + (session.visit_count !== 1 ? 's' : '') + '</div>';
            sessionsHtml += '</div>';
        });
        
        sessionsHtml += '</div></div>';
        return sessionsHtml;
    }
    
    // Render a single entry
    function renderEntry(entry) {
        const timeDisplay = formatTime12Hour(entry.time_usec);
        const title = escapeHtml(entry.title || entry.url);
        const url = escapeHtml(entry.url);
        const favicon = escapeHtml(entry.favicon_url || '');
        const titleLower = (entry.title || '').toLowerCase();
        const urlLower = entry.url.toLowerCase();
        const sessionAttr = entry.session_idx !== null && entry.session_idx !== undefined 
            ? `data-session-idx="${entry.session_idx}" data-date="${entry.date}"` 
            : '';
        
        return `
        <div class="entry" data-title="${titleLower}" data-url="${urlLower}" data-time-usec="${entry.time_usec || ''}" ${sessionAttr}>
            <div class="entry-time">${timeDisplay}</div>
        <div class="left">
                <img class="favicon" src="${favicon}" onerror="this.style.display='none'">
                <div class="entry-content">
                    <a class="title" href="${url}" target="_blank" rel="noopener noreferrer">${title}</a>
                    <span class="url">${url}</span>
            </div>
        </div>
        </div>`;
    }
    
    // Helper function to create date group header
    function createDateGroupHeader(entry, groupId) {
        const sessions = sessionsData[entry.date] || [];
        const sessionCount = sessions.length;
        // Use date-based ID for consistency across chunks
        const dateBasedId = 'date-group-' + entry.date.replace(/-/g, '');
        let headerHtml = `    <div class="date-group" data-date="${entry.date}" id="${dateBasedId}">\\n`;
        headerHtml += `        <div class="date-header">\\n`;
        headerHtml += `            <div class="date-header-left">${escapeHtml(entry.date_label)}</div>\\n`;
        headerHtml += `            <div class="date-header-middle">\\n`;
        if (sessionCount > 0) {
            const totalDuration = sessions.reduce((sum, s) => sum + s.duration_minutes, 0);
            headerHtml += `                <button class="session-toggle" onclick="toggleSessions('${dateBasedId}')" data-expanded="false">\\n`;
            headerHtml += `                    ▼ ${sessionCount} session${sessionCount !== 1 ? 's' : ''} (${formatDuration(totalDuration)})\\n`;
            headerHtml += `                </button>\\n`;
        }
        headerHtml += `            </div>\\n`;
        headerHtml += `            <div class="date-header-nav">\\n`;
        headerHtml += `                <button class="nav-button" onclick="jumpToPreviousDay('${entry.date}')" title="Previous day">‹</button>\\n`;
        // Right arrow - always rendered for consistent layout, but disabled/hidden when at today
        const today = new Date();
        const todayStr = today.toISOString().split('T')[0];
        const isToday = entry.date === todayStr;
        const nextDayDisabled = isToday ? 'disabled' : '';
        const nextDayContent = isToday ? '' : '›';
        headerHtml += `                <button class="nav-button next-day-btn" id="nextDayBtn-${dateBasedId}" onclick="jumpToNextDay('${entry.date}')" title="Next day" ${nextDayDisabled}>${nextDayContent}</button>\\n`;
        headerHtml += `                <button class="nav-button" onclick="jumpToToday()">Today</button>\\n`;
        headerHtml += `                <div class="date-picker-container">\\n`;
        headerHtml += `                    <button class="date-picker-trigger" onclick="toggleDatePicker(event)">\\n`;
        headerHtml += `                        <svg class="date-picker-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">\\n`;
        headerHtml += `                            <path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2z"/>\\n`;
        headerHtml += `                        </svg>\\n`;
        headerHtml += `                    </button>\\n`;
        headerHtml += `                    <div class="date-picker" id="datePicker-${dateBasedId}"></div>\\n`;
        headerHtml += `                </div>\\n`;
        headerHtml += `            </div>\\n`;
        headerHtml += `        </div>\\n`;
        if (sessionCount > 0) {
            headerHtml += renderSessionSummary(entry.date, dateBasedId);
        }
        return headerHtml;
    }
    
    // Navigation functions
    function jumpToDate(dateStr) {
        // If in search mode, clear search first to show all entries
        if (isSearchMode) {
            searchInput.value = '';
            filterHistory();
            // Wait for search to clear, then jump
            setTimeout(() => {
                jumpToDateAfterClear(dateStr);
            }, 100);
            return;
        }
        jumpToDateAfterClear(dateStr);
    }
    
    function jumpToDateAfterClear(dateStr) {
        // Find the first entry for this date in currentData
        const targetIndex = currentData.findIndex(entry => entry.date === dateStr);
        if (targetIndex === -1) {
            console.warn('Date not found in history:', dateStr);
            return;
        }
        
        // Check if we need to load more entries
        if (targetIndex >= renderedCount) {
            // Need to load entries up to this point
            loadEntriesUpToIndex(targetIndex).then(() => {
                scrollToDateGroup(dateStr);
                updateDayNavigationButtons();
            });
        } else {
            // Already rendered, just scroll
            scrollToDateGroup(dateStr);
            updateDayNavigationButtons();
        }
    }
    
    async function loadEntriesUpToIndex(targetIndex) {
        loadingIndicator.style.display = 'block';
        loadingIndicator.textContent = 'Loading entries...';
        try {
            while (renderedCount <= targetIndex && renderedCount < currentData.length) {
                const remaining = targetIndex - renderedCount + 1;
                const toLoad = Math.min(remaining, CHUNK_SIZE * 3);
                const html = renderChunk(currentData, renderedCount, toLoad);
                appendChunkHTML(html, renderedCount);
                renderedCount += toLoad;
                await new Promise(resolve => setTimeout(resolve, 10));
            }
        } finally {
            loadingIndicator.style.display = 'none';
        }
    }
    
    function scrollToDateGroup(dateStr) {
        const dateBasedId = 'date-group-' + dateStr.replace(/-/g, '');
        const dateGroup = document.getElementById(dateBasedId);
        if (dateGroup) {
            dateGroup.scrollIntoView({ behavior: 'smooth', block: 'start' });
            // Update navigation buttons after scroll completes
            setTimeout(() => {
                updateDayNavigationButtons();
            }, 500);
        }
    }
    
    function jumpToToday() {
        const today = new Date();
        const todayStr = today.toISOString().split('T')[0];
        jumpToDate(todayStr);
        updateDayNavigationButtons();
    }
    
    function getCurrentViewDate() {
        // Find the date group that's currently at the top of the viewport (sticky header)
        const dateGroups = Array.from(document.querySelectorAll('.date-group'));
        const viewportTop = window.scrollY;
        
        for (const group of dateGroups) {
            const rect = group.getBoundingClientRect();
            const header = group.querySelector('.date-header');
            if (header) {
                const headerRect = header.getBoundingClientRect();
                // Check if this header is sticky (at top of viewport)
                if (headerRect.top <= 10 && headerRect.bottom > 0) {
                    const dateStr = group.getAttribute('data-date');
                    if (dateStr) {
                        return dateStr;
                    }
                }
            }
        }
        
        // Fallback: use first rendered entry's date
        if (currentData.length > 0 && renderedCount > 0) {
            const firstRenderedEntry = currentData[0];
            if (firstRenderedEntry && firstRenderedEntry.date) {
                return firstRenderedEntry.date;
            }
        }
        
        // Last fallback: today
        return new Date().toISOString().split('T')[0];
    }
    
    function jumpToPreviousDay(fromDateStr) {
        // Use the date from the button's context (the date header it's in)
        const currentDate = new Date(fromDateStr + 'T00:00:00');
        
        // Go to previous day
        currentDate.setDate(currentDate.getDate() - 1);
        const previousDayStr = currentDate.toISOString().split('T')[0];
        jumpToDate(previousDayStr);
    }
    
    function jumpToNextDay(fromDateStr) {
        // Use the date from the button's context (the date header it's in)
        const today = new Date();
        const todayStr = today.toISOString().split('T')[0];
        
        // Check if we're at today - if so, don't do anything
        if (fromDateStr >= todayStr) {
            return; // Already at or past today, can't go forward
        }
        
        const currentDate = new Date(fromDateStr + 'T00:00:00');
        // Go to next day
        currentDate.setDate(currentDate.getDate() + 1);
        const nextDayStr = currentDate.toISOString().split('T')[0];
        jumpToDate(nextDayStr);
    }
    
    function updateDayNavigationButtons() {
        // Update next day button state based on date group's date
        const today = new Date();
        const todayStr = today.toISOString().split('T')[0];
        
        // Get all date groups and update their next day buttons based on their date
        const dateGroups = Array.from(document.querySelectorAll('.date-group'));
        dateGroups.forEach(group => {
            const dateStr = group.getAttribute('data-date');
            const nextDayBtn = group.querySelector('.next-day-btn');
            if (nextDayBtn && dateStr) {
                // Disable and grey out if this date group is for today or future
                if (dateStr >= todayStr) {
                    nextDayBtn.disabled = true;
                    nextDayBtn.textContent = '›';
                    // CSS will handle the greyed out appearance via :disabled styles
                } else {
                    nextDayBtn.disabled = false;
                    nextDayBtn.textContent = '›';
                    // CSS will handle the normal appearance
                }
            }
        });
    }
    
    // Date picker functions
    let currentPickerId = null;
    
    function toggleDatePicker(event) {
        event.stopPropagation();
        const trigger = event.target.closest('.date-picker-trigger');
        if (!trigger) return;
        
        const container = trigger.closest('.date-picker-container');
        const picker = container.querySelector('.date-picker');
        const pickerId = picker.id;
        
        // Close other pickers
        if (currentPickerId && currentPickerId !== pickerId) {
            const otherPicker = document.getElementById(currentPickerId);
            if (otherPicker) {
                otherPicker.classList.remove('show');
            }
        }
        
        // Toggle current picker
        if (picker.classList.contains('show')) {
            picker.classList.remove('show');
            currentPickerId = null;
        } else {
            picker.classList.add('show');
            currentPickerId = pickerId;
            // Initialize picker if empty
            if (!picker.innerHTML.trim()) {
                const now = new Date();
                let initMonth = now.getMonth();
                let initYear = now.getFullYear();
                
                // Ensure initial month/year is within available data range
                if (initYear < minYear || (initYear === minYear && initMonth < minMonth)) {
                    initYear = minYear;
                    initMonth = minMonth;
                } else if (initYear > maxYear || (initYear === maxYear && initMonth > maxMonth)) {
                    initYear = maxYear;
                    initMonth = maxMonth;
                }
                
                renderDatePicker(picker, initMonth, initYear);
            }
        }
    }
    
    function renderDatePicker(pickerElement, month, year) {
        const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December'];
        const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        
        // Get first day of month and number of days
        const firstDay = new Date(year, month, 1).getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const today = new Date();
        const isTodayMonth = month === today.getMonth() && year === today.getFullYear();
        const todayDate = isTodayMonth ? today.getDate() : null;
        
        let html = '<div class="date-picker-header">';
        html += '<div class="date-picker-month-year">';
        html += '<select class="date-picker-month-select" onchange="changeDatePickerMonth(this)" onclick="event.stopPropagation()">';
        
        // Only show months that have data for the selected year
        // If it's the min year, start from minMonth; if it's the max year, end at maxMonth
        const startMonth = (year === minYear) ? minMonth : 0;
        const endMonth = (year === maxYear) ? maxMonth : 11;
        
        for (let i = startMonth; i <= endMonth; i++) {
            html += `<option value="${i}" ${i === month ? 'selected' : ''}>${monthNames[i]}</option>`;
        }
        html += '</select>';
        html += '<select class="date-picker-year-select" onchange="changeDatePickerYear(this)" onclick="event.stopPropagation()">';
        // Only show years that have data
        for (let y = maxYear; y >= minYear; y--) {
            html += `<option value="${y}" ${y === year ? 'selected' : ''}>${y}</option>`;
        }
        html += '</select>';
        html += '</div>';
        html += '<div>';
        html += `<button class="date-picker-nav" onclick="event.stopPropagation(); resetDatePickerToCurrent()" title="Reset to current month">⟳</button>`;
        html += `<button class="date-picker-nav" onclick="event.stopPropagation(); navigateDatePickerMonth(-1)">‹</button>`;
        html += `<button class="date-picker-nav" onclick="event.stopPropagation(); navigateDatePickerMonth(1)">›</button>`;
        html += '</div>';
        html += '</div>';
        
        // Day headers
        html += '<div class="date-picker-grid">';
        dayNames.forEach(day => {
            html += `<div class="date-picker-day-header">${day}</div>`;
        });
        
        // Empty cells for days before month starts
        for (let i = 0; i < firstDay; i++) {
            html += '<div class="date-picker-day other-month"></div>';
        }
        
        // Days of the month
        for (let day = 1; day <= daysInMonth; day++) {
            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            const hasEntries = availableDates.has(dateStr);
            const isToday = day === todayDate;
            const classes = ['date-picker-day'];
            
            if (hasEntries) {
                classes.push('has-entries');
            } else {
                classes.push('no-entries');
            }
            
            if (isToday) {
                classes.push('today');
            }
            
            // Only add click handler if date has entries
            const onclickAttr = hasEntries 
                ? `onclick="event.stopPropagation(); selectDate('${dateStr}')"` 
                : '';
            
            html += `<div class="${classes.join(' ')}" data-date="${dateStr}" ${onclickAttr}>${day}</div>`;
        }
        
        // Fill remaining cells
        const totalCells = firstDay + daysInMonth;
        const remainingCells = 42 - totalCells; // 6 rows * 7 days
        for (let i = 0; i < remainingCells && i < 7; i++) {
            html += '<div class="date-picker-day other-month"></div>';
        }
        
        html += '</div>';
        
        pickerElement.innerHTML = html;
        pickerElement.dataset.month = month;
        pickerElement.dataset.year = year;
    }
    
    function changeDatePickerMonth(select) {
        const picker = select.closest('.date-picker');
        const year = parseInt(picker.dataset.year);
        const month = parseInt(select.value);
        renderDatePicker(picker, month, year);
    }
    
    function changeDatePickerYear(select) {
        const picker = select.closest('.date-picker');
        const currentMonth = parseInt(picker.dataset.month);
        const year = parseInt(select.value);
        
        // Adjust month if it's out of range for the selected year
        let month = currentMonth;
        if (year === minYear && currentMonth < minMonth) {
            month = minMonth;
        } else if (year === maxYear && currentMonth > maxMonth) {
            month = maxMonth;
        }
        
        renderDatePicker(picker, month, year);
    }
    
    function navigateDatePickerMonth(direction) {
        const picker = document.getElementById(currentPickerId);
        if (!picker) return;
        let month = parseInt(picker.dataset.month);
        let year = parseInt(picker.dataset.year);
        month += direction;
        
        // Check bounds based on available data
        if (month < 0) {
            if (year > minYear) {
                month = 11;
                year--;
                // If we moved to a new year, check if we need to adjust month
                if (year === minYear && month < minMonth) {
                    month = minMonth;
                }
            } else {
                // Can't go earlier than minYear/minMonth
                month = 0;
            }
        } else if (month > 11) {
            if (year < maxYear) {
                month = 0;
                year++;
                // If we moved to a new year, check if we need to adjust month
                if (year === maxYear && month > maxMonth) {
                    month = maxMonth;
                }
            } else {
                // Can't go later than maxYear/maxMonth
                month = 11;
            }
        } else {
            // Check if month is within bounds for current year
            if (year === minYear && month < minMonth) {
                month = minMonth;
            } else if (year === maxYear && month > maxMonth) {
                month = maxMonth;
            }
        }
        
        renderDatePicker(picker, month, year);
    }
    
    function resetDatePickerToCurrent() {
        const picker = document.getElementById(currentPickerId);
        if (!picker) return;
        const today = new Date();
        let currentMonth = today.getMonth();
        let currentYear = today.getFullYear();
        
        // Ensure current month/year is within available data range
        if (currentYear < minYear || (currentYear === minYear && currentMonth < minMonth)) {
            currentYear = minYear;
            currentMonth = minMonth;
        } else if (currentYear > maxYear || (currentYear === maxYear && currentMonth > maxMonth)) {
            currentYear = maxYear;
            currentMonth = maxMonth;
        }
        
        renderDatePicker(picker, currentMonth, currentYear);
    }
    
    function selectDate(dateStr) {
        jumpToDate(dateStr);
        // Close picker
        if (currentPickerId) {
            const picker = document.getElementById(currentPickerId);
            if (picker) {
                picker.classList.remove('show');
            }
            currentPickerId = null;
        }
    }
    
    // Close date picker when clicking outside
    document.addEventListener('click', function(e) {
        if (currentPickerId) {
            // Check if click is outside both the container and the picker itself
            const container = e.target.closest('.date-picker-container');
            const picker = document.getElementById(currentPickerId);
            const isInsidePicker = picker && (picker.contains(e.target) || e.target === picker);
            
            if (!container && !isInsidePicker) {
                picker.classList.remove('show');
                currentPickerId = null;
            }
        }
    });
    
    // Handle scroll-based header compact state
    const topHeader = document.getElementById('topHeader');
    const pageTitle = document.getElementById('pageTitle');
    
    function updateHeaderCompactState() {
        if (window.scrollY > 0) {
            topHeader.classList.add('compact');
            pageTitle.classList.add('compact');
            document.body.classList.add('compact-header');
        } else {
            topHeader.classList.remove('compact');
            pageTitle.classList.remove('compact');
            document.body.classList.remove('compact-header');
        }
    }
    
    // Initial check
    updateHeaderCompactState();
    
    // Listen for scroll events
    window.addEventListener('scroll', updateHeaderCompactState, { passive: true });
    
    // Track which date-group containers are currently open
    let openDateGroups = new Set();
    
    // Render entries in chunks
    function renderChunk(data, startIndex, count) {
        const endIndex = Math.min(startIndex + count, data.length);
        if (startIndex >= endIndex) return '';
        
        let html = '';
        let currentDate = null;
        let dateGroupId = 0;
        let openedGroupId = null;
        let createdInitialHeader = false;
        let lastDateWithEntries = null; // Track the last date that actually had entries rendered
        let groupsCreatedInThisChunk = []; // Track all groups we created in this chunk
        
        // Check if we need to start a new date group or continue the previous one
        const firstEntry = data[startIndex];
        const shouldCreateHeader = (lastRenderedDate === null || lastRenderedDate !== firstEntry.date);
        
        console.log('[renderChunk]', {
            startIndex,
            count,
            firstEntryDate: firstEntry.date,
            lastRenderedDate,
            shouldCreateHeader
        });
        
        if (shouldCreateHeader) {
            // Start new date group
            const dateBasedId = 'date-group-' + firstEntry.date.replace(/-/g, '');
            html += createDateGroupHeader(firstEntry, dateBasedId);
            currentDate = firstEntry.date;
            openedGroupId = dateBasedId;
            createdInitialHeader = true;
            groupsCreatedInThisChunk.push(dateBasedId);
            openDateGroups.add(dateBasedId);
            console.log('[renderChunk] Created new date group:', dateBasedId);
        } else {
            // Continue previous date group - no header needed, container should already be open
            currentDate = firstEntry.date;
            const dateBasedId = 'date-group-' + firstEntry.date.replace(/-/g, '');
            openedGroupId = dateBasedId;
            createdInitialHeader = false;
            console.log('[renderChunk] Continuing date group:', dateBasedId);
            // Don't create header HTML - entries will be appended to existing container
        }
        
        // Render entries
        for (let i = startIndex; i < endIndex; i++) {
            const entry = data[i];
            
            // Check if date changed within this chunk
            if (currentDate !== entry.date) {
                // Only close groups that were NOT created in this chunk
                // If we created it in this chunk, we'll handle closing at the end if needed
                const wasCreatedInThisChunk = groupsCreatedInThisChunk.includes(openedGroupId);
                
                if (createdInitialHeader && openedGroupId && !wasCreatedInThisChunk) {
                    // We created this group in a previous chunk's HTML, so we can close it in HTML
                    html += '    </div>\\n';
                    openDateGroups.delete(openedGroupId);
                    console.log('[renderChunk] Closed date group in HTML (date changed, from previous chunk):', openedGroupId);
                } else if (openedGroupId && wasCreatedInThisChunk) {
                    // We created this group in this chunk - don't close it yet, handle at end
                    console.log('[renderChunk] Date changed but not closing in HTML (created in this chunk):', openedGroupId);
                } else if (openedGroupId) {
                    // We're continuing - don't close in HTML, container is already in DOM
                    console.log('[renderChunk] Date changed but not closing in HTML (continuing):', openedGroupId);
                }
                
                // Start new date group
                const dateBasedId = 'date-group-' + entry.date.replace(/-/g, '');
                html += createDateGroupHeader(entry, dateBasedId);
                currentDate = entry.date;
                openedGroupId = dateBasedId;
                createdInitialHeader = true; // We're now creating a new header
                groupsCreatedInThisChunk.push(dateBasedId);
                openDateGroups.add(dateBasedId);
                console.log('[renderChunk] Started new date group (date changed):', dateBasedId);
            }
            
            html += renderEntry(entry);
            lastDateWithEntries = entry.date; // Track the last date that had entries
        }
        
        // Update lastRenderedDate to the last date that actually had entries rendered
        if (lastDateWithEntries !== null) {
            lastRenderedDate = lastDateWithEntries;
        } else if (currentDate !== null) {
            // Fallback to currentDate if no entries were rendered (shouldn't happen)
            lastRenderedDate = currentDate;
        }
        
        // Determine if we should close the date-group container
        // Use lastDateWithEntries (or currentDate) for the check
        const dateToCheck = lastDateWithEntries || currentDate;
        const nextEntryExists = endIndex < data.length;
        const nextEntrySameDate = nextEntryExists && dateToCheck !== null && data[endIndex].date === dateToCheck;
        const shouldClose = !nextEntrySameDate; // Close if next entry is different date or no more entries
        
        console.log('[renderChunk] Closing decision:', {
            currentDate,
            lastDateWithEntries,
            dateToCheck,
            nextEntryExists,
            nextEntryDate: nextEntryExists ? data[endIndex].date : 'N/A',
            nextEntrySameDate,
            shouldClose,
            openedGroupId,
            createdInitialHeader,
            groupsCreatedInThisChunk
        });
        
        // Close groups we created in this chunk, but only if appropriate
        // We need to close all but the last one (if dates changed), or the last one if shouldClose
        if (groupsCreatedInThisChunk.length > 1) {
            // Multiple groups created - close all but the last one
            for (let i = 0; i < groupsCreatedInThisChunk.length - 1; i++) {
                const groupId = groupsCreatedInThisChunk[i];
                html += '    </div>\\n';
                openDateGroups.delete(groupId);
                console.log('[renderChunk] Closed intermediate date group:', groupId);
            }
        }
        
        // Handle the last group we created/opened
        if (shouldClose && openedGroupId && createdInitialHeader) {
            // Only close if we created this group in HTML (not if we're continuing)
            html += '    </div>\\n';
            openDateGroups.delete(openedGroupId);
            console.log('[renderChunk] Closed date group:', openedGroupId);
        } else if (openedGroupId) {
            if (createdInitialHeader) {
                console.log('[renderChunk] Leaving date group open:', openedGroupId);
            } else {
                console.log('[renderChunk] Not closing (continuing previous group):', openedGroupId);
            }
        }
        // If shouldClose is false, leave container open for next chunk
        
        return html;
    }
    
    // Toggle session summary visibility
    function toggleSessions(groupId, animate = true) {
        const group = document.getElementById(groupId);
        if (!group) {
            console.warn('Date group not found:', groupId);
            return;
        }
        const summary = group.querySelector('.session-summary');
        const toggle = group.querySelector('.session-toggle');
        if (!summary) {
            console.warn('Session summary not found in group:', groupId);
            return;
        }
        if (!toggle) {
            console.warn('Session toggle not found in group:', groupId);
            return;
        }
        const isExpanded = toggle.getAttribute('data-expanded') === 'true';
        
        if (isExpanded && animate) {
            // Closing - add closing class for animation
            summary.classList.add('closing');
            // After animation completes, hide it and remove clipping
            setTimeout(() => {
                summary.style.display = 'none';
                summary.classList.remove('closing');
                summary.classList.remove('clipped');
                summary.style.clipPath = '';
                // Remove from collapsing set after collapse completes
                const groupId = group.id;
                if (groupId) {
                    collapsingSummaries.delete(groupId);
                }
            }, 150); // Match CSS transition duration (0.15s)
        } else {
            // Opening - remove closing class and show
            summary.classList.remove('closing');
            summary.style.display = 'block';
            // Force reflow to ensure display change takes effect before animation
            summary.offsetHeight;
        }
        
        toggle.setAttribute('data-expanded', !isExpanded ? 'true' : 'false');
        // Update toggle icon
        const currentText = toggle.textContent.trim();
        const newIcon = isExpanded ? '▼' : '▲';
        toggle.textContent = currentText.replace(/▼|▲/, newIcon);
    }
    
    // Make toggleSessions available globally
    window.toggleSessions = toggleSessions;
    
    // Clip or collapse session summaries based on header overlap
    function handleSessionSummaryOverlap() {
        // Get all date-groups in order
        const allDateGroups = Array.from(document.querySelectorAll('.date-group'));
        
        // Find all visible (expanded) session summaries
        const visibleSummaries = Array.from(document.querySelectorAll('.session-summary')).filter(summary => {
            const style = summary.getAttribute('style') || '';
            const isHidden = style.includes('display: none');
            return !isHidden && summary.offsetParent !== null;
        });
        
        if (visibleSummaries.length === 0) return;
        
        // For each visible summary, check overlap with the next day's header
        visibleSummaries.forEach(summary => {
            const summaryGroup = summary.closest('.date-group');
            if (!summaryGroup) return;
            
            const summaryGroupId = summaryGroup.id;
            const summaryIndex = allDateGroups.indexOf(summaryGroup);
            
            // Get the summary's current position
            const summaryRect = summary.getBoundingClientRect();
            const summaryTop = summaryRect.top;
            const summaryBottom = summaryRect.bottom;
            const summaryHeight = summaryRect.height;
            
            // Find the next date-header (from the immediately following date-group)
            let shouldCollapse = false;
            let clipHeight = summaryHeight; // Default: no clipping
            
            for (let i = summaryIndex + 1; i < allDateGroups.length; i++) {
                const laterGroup = allDateGroups[i];
                const laterHeader = laterGroup.querySelector('.date-header');
                if (!laterHeader) continue;
                
                const headerRect = laterHeader.getBoundingClientRect();
                const headerTop = headerRect.top;
                const headerBottom = headerRect.bottom;
                
                // Check if the header overlaps with the summary
                if (summaryBottom > headerTop && summaryTop < headerBottom) {
                    // Calculate visible height (from top of summary to where header starts)
                    const visibleHeight = Math.max(0, headerTop - summaryTop);
                    
                    // Collapse when only the margin/padding is visible (nothing useful to see)
                    // The summary has 16px padding, so if visible height is less than ~20-24px,
                    // we're just seeing padding/margin and should collapse
                    const collapseThreshold = 24; // pixels - roughly padding + small margin
                    
                    // During fast scrolling, be more aggressive - collapse sooner
                    const adjustedThreshold = scrollVelocity > 5 ? 40 : collapseThreshold;
                    
                    if (visibleHeight <= adjustedThreshold) {
                        shouldCollapse = true;
                        // Keep the current clip applied until collapse happens
                        // Don't set clipHeight here - let the collapse logic handle it
                        break;
                    }
                    
                    // Otherwise, clip the covered portion (bottom part that's under the header)
                    clipHeight = visibleHeight;
                } else if (summaryTop < headerBottom && summaryBottom > headerTop) {
                    // Summary is fully or mostly covered - check if top is near header bottom
                    // This handles the case where summary might be completely under header
                    const distanceFromHeaderBottom = headerBottom - summaryTop;
                    // During fast scrolling, be more aggressive
                    const adjustedDistance = scrollVelocity > 5 ? 40 : 24;
                    if (distanceFromHeaderBottom <= adjustedDistance) {
                        shouldCollapse = true;
                        break;
                    }
                } else if (summaryTop >= headerBottom && scrollVelocity > 5) {
                    // During fast scrolling, if summary has passed completely under header, collapse it
                    // This catches cases where we scrolled past too fast to detect overlap
                    shouldCollapse = true;
                    break;
                }
                
                // Only check the immediately next date-group's header
                break;
            }
            
            // Apply clipping or collapse
            const toggle = summaryGroup.querySelector('.session-toggle');
            if (!toggle) return;
            
            // Check if summary is currently collapsed
            const isExpanded = toggle.getAttribute('data-expanded') === 'true';
            
            if (shouldCollapse) {
                // Fully collapse if only margin/padding is visible or top is covered
                if (isExpanded && !collapsingSummaries.has(summaryGroupId)) {
                    collapsingSummaries.add(summaryGroupId);
                    toggleSessions(summaryGroupId);
                }
                // Keep clipping applied until collapse animation completes
                // Don't remove clip here - it will be removed when display: none is applied
            } else if (clipHeight < summaryHeight && clipHeight > 0) {
                // Clip the covered portion only if there's meaningful content visible
                const collapseThreshold = 24;
                if (clipHeight > collapseThreshold) {
                    // Apply clipping - keep it applied
                    summary.classList.add('clipped');
                    // Use clip-path to hide the bottom portion that's covered
                    const clipPercent = ((summaryHeight - clipHeight) / summaryHeight) * 100;
                    summary.style.clipPath = `inset(0 0 ${clipPercent}% 0)`;
                } else {
                    // Visible portion is too small - collapse instead of clipping
                    // But keep any existing clip applied to prevent flash
                    if (isExpanded && !collapsingSummaries.has(summaryGroupId)) {
                        collapsingSummaries.add(summaryGroupId);
                        toggleSessions(summaryGroupId);
                    }
                    // Don't remove clip here - let it stay until collapse
                }
            } else {
                // No clipping needed - only remove if we're not collapsing and not in collapse process
                // Check if summary is far enough from header to safely remove clip
                if (!shouldCollapse && !collapsingSummaries.has(summaryGroupId)) {
                    summary.classList.remove('clipped');
                    summary.style.clipPath = '';
                }
            }
        });
    }
    
    // Track summaries that are currently collapsing to prevent race conditions
    const collapsingSummaries = new Set();
    
    // Track scroll velocity to detect fast scrolling
    let lastScrollTop = window.scrollY;
    let lastScrollTime = Date.now();
    let scrollVelocity = 0;
    
    // Use requestAnimationFrame for smooth, frame-synced updates during normal scrolling
    let rafId = null;
    function throttledOverlapCheck() {
        // Calculate scroll velocity
        const currentScrollTop = window.scrollY;
        const currentTime = Date.now();
        const timeDelta = currentTime - lastScrollTime;
        if (timeDelta > 0) {
            scrollVelocity = Math.abs(currentScrollTop - lastScrollTop) / timeDelta;
        }
        lastScrollTop = currentScrollTop;
        lastScrollTime = currentTime;
        
        // During fast scrolling, do immediate check + RAF
        // During normal scrolling, just use RAF
        if (scrollVelocity > 5) { // pixels per millisecond threshold for "fast" scrolling
            // Fast scrolling - do immediate check
            handleSessionSummaryOverlap();
        }
        
        // Always queue RAF for smooth updates
        if (rafId !== null) {
            cancelAnimationFrame(rafId);
        }
        rafId = requestAnimationFrame(() => {
            handleSessionSummaryOverlap();
            rafId = null;
        });
    }
    
    // Check on scroll end to catch any summaries that were missed during fast scrolling
    let scrollEndTimeout = null;
    function handleScrollEnd() {
        if (scrollEndTimeout) {
            clearTimeout(scrollEndTimeout);
        }
        scrollEndTimeout = setTimeout(() => {
            // Final check when scrolling stops
            handleSessionSummaryOverlap();
            scrollVelocity = 0; // Reset velocity
        }, 150); // Wait 150ms after last scroll event
    }
    
    // Throttle day navigation button updates
    let navButtonUpdateTimeout = null;
    function throttledNavButtonUpdate() {
        if (navButtonUpdateTimeout) {
            clearTimeout(navButtonUpdateTimeout);
        }
        navButtonUpdateTimeout = setTimeout(() => {
            updateDayNavigationButtons();
        }, 100);
    }
    
    // Set up scroll listener to handle summary overlap
    window.addEventListener('scroll', () => {
        throttledOverlapCheck();
        handleScrollEnd();
        // Update day navigation buttons on scroll (throttled)
        throttledNavButtonUpdate();
    }, { passive: true });
    
    // Set up event delegation for session navigation
    document.addEventListener('click', function(e) {
        // Check if clicked on session time start/end
        if (e.target.classList.contains('session-time-start') || e.target.classList.contains('session-time-end')) {
            e.stopPropagation();
            const dateStr = e.target.getAttribute('data-date');
            const sessionIdx = parseInt(e.target.getAttribute('data-session-idx'));
            const position = e.target.getAttribute('data-position');
            scrollToSession(dateStr, sessionIdx, position);
            return;
        }
        
        // Check if clicked on session item (but not on the times)
        if (e.target.closest('.session-item') && !e.target.closest('.session-time')) {
            const item = e.target.closest('.session-item');
            const dateStr = item.getAttribute('data-date');
            const sessionIdx = parseInt(item.getAttribute('data-session-idx'));
            const position = item.getAttribute('data-position') || 'end';
            scrollToSession(dateStr, sessionIdx, position);
        }
    });
    
    // Load entries up to a specific time for a date
    async function loadEntriesUpToTime(targetTime, dateStr) {
        // Check if we need to load more entries
        if (renderedCount >= currentData.length) {
            return; // All entries already loaded
        }
        
        // Find the latest index we need to load to include the target time
        // Data is sorted newest first, so we need to find where targetTime fits
        let targetIndex = -1;
        for (let i = 0; i < currentData.length; i++) {
            const entry = currentData[i];
            if (entry.date === dateStr && entry.time_usec) {
                // Since data is sorted newest first, we need to load until we find entries <= targetTime
                if (entry.time_usec <= targetTime) {
                    targetIndex = i;
                    // Continue to find the last entry for this date that's <= targetTime
                } else if (targetIndex !== -1 && entry.date !== dateStr) {
                    // We've moved to a different date, stop
                    break;
                }
            }
        }
        
        // If we found a target, ensure we load up to at least that index
        // Also load a bit extra to ensure we have context
        const loadUntil = targetIndex !== -1 ? Math.min(targetIndex + 20, currentData.length - 1) : currentData.length - 1;
        
        // Load entries in chunks until we reach the target
        while (renderedCount <= loadUntil && renderedCount < currentData.length) {
            const remaining = loadUntil - renderedCount + 1;
            const toLoad = Math.min(remaining, CHUNK_SIZE * 3); // Load larger chunks for navigation
            const html = renderChunk(currentData, renderedCount, toLoad);
            
            // Use shared helper to append HTML with date-group continuation logic
            appendChunkHTML(html, renderedCount);
            
            renderedCount += toLoad;
            
            // Re-add sentinel if needed
            if (renderedCount < currentData.length) {
                addSentinel();
            }
            
            // Small delay to prevent blocking UI
            await new Promise(resolve => setTimeout(resolve, 10));
        }
    }
    
    // Scroll to session start or end
    async function scrollToSession(dateStr, sessionIdx, position) {
        const sessions = sessionsData[dateStr] || [];
        if (sessionIdx >= sessions.length) return;
        
        const session = sessions[sessionIdx];
        const targetTime = position === 'start' ? session.start_time_usec : session.end_time_usec;
        
        // Show loading indicator
        loadingIndicator.style.display = 'block';
        loadingIndicator.textContent = 'Loading entries...';
        
        try {
            // First, ensure entries up to the target time are loaded
            await loadEntriesUpToTime(targetTime, dateStr);
            
            // Now try to find entries
            let entries = Array.from(document.querySelectorAll(`.entry[data-date="${dateStr}"][data-session-idx="${sessionIdx}"]`));
            
            // If no entries found by session index, find by time range
            if (entries.length === 0) {
                const allDateEntries = Array.from(document.querySelectorAll(`.entry[data-date="${dateStr}"]`));
                entries = allDateEntries.filter(entry => {
                    const entryTime = parseInt(entry.getAttribute('data-time-usec') || '0');
                    return entryTime >= session.start_time_usec && entryTime <= session.end_time_usec;
                });
            }
            
            // If still no entries, try exact time match
            if (entries.length === 0) {
                const exactMatch = document.querySelector(`.entry[data-time-usec="${targetTime}"]`);
                if (exactMatch) {
                    exactMatch.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    loadingIndicator.style.display = 'none';
                    return;
                }
                loadingIndicator.style.display = 'none';
                return;
            }
            
            // Sort entries by time to ensure correct order
            entries.sort((a, b) => {
                const timeA = parseInt(a.getAttribute('data-time-usec') || '0');
                const timeB = parseInt(b.getAttribute('data-time-usec') || '0');
                return timeA - timeB;
            });
            
            // Scroll to first or last entry in session
            if (position === 'start') {
                entries[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
            } else {
                entries[entries.length - 1].scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        } finally {
            loadingIndicator.style.display = 'none';
        }
    }
    
    // Make scrollToSession available globally
    window.scrollToSession = scrollToSession;
    
    // Intersection Observer for infinite scroll
    let sentinel = null;
    let observer = null;
    let isLoading = false;
    
    function addSentinel() {
        if (sentinel) {
            sentinel.remove();
        }
        sentinel = document.createElement('div');
        sentinel.style.height = '1px';
        sentinel.id = 'scrollSentinel';
        historyContainer.appendChild(sentinel);
        if (observer) {
            observer.observe(sentinel);
        }
    }
    
    function setupInfiniteScroll() {
        if (observer) {
            observer.disconnect();
        }
        
        observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && !isSearchMode && !isLoading && renderedCount < currentData.length) {
                isLoading = true;
                loadingIndicator.style.display = 'block';
                setTimeout(() => {
                    loadEntries();
                    isLoading = false;
                }, 50);
            }
        }, { threshold: 0.1, rootMargin: '100px' });
        
        addSentinel();
    }
    
    // Helper function to append chunk HTML, handling date-group continuation
    function appendChunkHTML(html, firstEntryIndex) {
        if (firstEntryIndex >= currentData.length) {
            return;
        }
        
        const firstEntry = currentData[firstEntryIndex];
        if (!firstEntry) return;
        
        // Check if we're continuing a date group by checking if the first entry's date
        // has an open date-group container in the DOM
        // This is more reliable than comparing to lastRenderedDate, which may have changed
        // if the date changed within the chunk
        const dateBasedId = 'date-group-' + firstEntry.date.replace(/-/g, '');
        const openGroup = document.getElementById(dateBasedId);
        
        if (openGroup && firstEntryIndex > 0) {
            // We found an open date-group for this date - we're continuing it
            console.log('[appendChunkHTML] Continuing same date:', {
                dateBasedId,
                openGroupFound: true,
                firstEntryIndex,
                firstEntryDate: firstEntry.date
            });
            // Append entries to the open date-group container (before its closing tag)
            openGroup.insertAdjacentHTML('beforeend', html);
            return;
        }
        
        // New date or first load, append normally
        console.log('[appendChunkHTML] New date or first load, appending to historyContainer', {
            firstEntryDate: firstEntry.date,
            lastRenderedDate,
            openGroupFound: !!openGroup
        });
        historyContainer.insertAdjacentHTML('beforeend', html);
    }
    
    // Load and render entries
    function loadEntries(chunkSize = null) {
        if (renderedCount >= currentData.length) {
            loadingIndicator.style.display = 'none';
            if (sentinel) {
                sentinel.remove();
            }
            return;
        }
        
        const size = chunkSize || CHUNK_SIZE;
        const toRender = Math.min(size, currentData.length - renderedCount);
        if (toRender <= 0) {
            loadingIndicator.style.display = 'none';
            if (sentinel) {
                sentinel.remove();
            }
            return;
        }
        
        const html = renderChunk(currentData, renderedCount, toRender);
        
        console.log('[loadEntries]', {
            renderedCount,
            toRender,
            lastRenderedDate,
            htmlLength: html.length,
            firstEntryDate: renderedCount < currentData.length ? currentData[renderedCount].date : 'N/A'
        });
        
        // Use shared helper to append HTML with date-group continuation logic
        appendChunkHTML(html, renderedCount);
        
        renderedCount += toRender;
        
        // Re-add sentinel at the bottom after loading
        if (renderedCount < currentData.length) {
            addSentinel();
            loadingIndicator.style.display = 'none';
        } else {
            loadingIndicator.style.display = 'none';
            if (sentinel) {
                sentinel.remove();
            }
        }
    }
    
    // Debounce utility function
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    // Search functionality
    function filterHistory() {
        const searchTerm = searchInput.value.toLowerCase().trim();
        
        if (searchTerm === '') {
            // Reset to normal mode immediately (no debounce for clearing)
            isSearchMode = false;
            currentData = historyData;
            historyContainer.innerHTML = '';
            renderedCount = 0;
            lastRenderedDate = null;  // Reset last rendered date
            setupInfiniteScroll();
            loadEntries(INITIAL_LOAD);
            noResults.style.display = 'none';
            loadingIndicator.style.display = 'none';
            return;
        }
        
        // Show loading indicator while filtering
        loadingIndicator.style.display = 'block';
        historyContainer.innerHTML = '';
        
        // Use requestAnimationFrame to defer heavy work and keep UI responsive
        requestAnimationFrame(() => {
            // Filter data
            isSearchMode = true;
            if (observer) {
                observer.disconnect();
            }
            if (sentinel) {
                sentinel.remove();
            }
            
            // Defer the expensive filtering operation to next event loop tick
            setTimeout(() => {
                filteredData = historyData.filter(entry => {
                    const title = (entry.title || '').toLowerCase();
                    const url = entry.url.toLowerCase();
                    return title.includes(searchTerm) || url.includes(searchTerm);
                });
                
                currentData = filteredData;
                renderedCount = 0;
                lastRenderedDate = null;  // Reset last rendered date for search results
                
                if (filteredData.length === 0) {
                    noResults.style.display = 'block';
                    loadingIndicator.style.display = 'none';
                } else {
                    noResults.style.display = 'none';
                    // Render all filtered results (search results are typically smaller)
                    const html = renderChunk(filteredData, 0, filteredData.length);
                    historyContainer.innerHTML = html;
                    renderedCount = filteredData.length;
                    loadingIndicator.style.display = 'none';
                }
            }, 0);
        });
    }
    
    // Debounce search with 300ms delay, but handle empty search immediately
    let debounceTimeout;
    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase().trim();
        
        // Clear any pending debounced search
        if (debounceTimeout) {
            clearTimeout(debounceTimeout);
        }
        
        // If search is empty, execute immediately
        if (searchTerm === '') {
            filterHistory();
        } else {
            // Otherwise, debounce the search
            debounceTimeout = setTimeout(() => {
                filterHistory();
            }, 300);
        }
    });
    
    // Initial load - load first chunk, then set up infinite scroll
    loadEntries(INITIAL_LOAD);
    setupInfiniteScroll();
    
    // Update day navigation buttons after initial load
    setTimeout(() => {
        updateDayNavigationButtons();
    }, 100);

    // Theme toggle functionality
    const themeToggle = document.getElementById('themeToggle');
    const moonIcon = document.getElementById('moonIcon');
    const sunIcon = document.getElementById('sunIcon');
    const themeText = document.getElementById('themeText');
    const htmlElement = document.documentElement;

    // Load saved theme preference
    const savedTheme = localStorage.getItem('theme') || 'light';
    if (savedTheme === 'dark') {
        htmlElement.setAttribute('data-theme', 'dark');
        moonIcon.style.display = 'none';
        sunIcon.style.display = 'block';
        themeText.textContent = 'Light';
    }

    themeToggle.addEventListener('click', () => {
        const currentTheme = htmlElement.getAttribute('data-theme');
        if (currentTheme === 'dark') {
            htmlElement.removeAttribute('data-theme');
            moonIcon.style.display = 'block';
            sunIcon.style.display = 'none';
            themeText.textContent = 'Dark';
            localStorage.setItem('theme', 'light');
        } else {
            htmlElement.setAttribute('data-theme', 'dark');
            moonIcon.style.display = 'none';
            sunIcon.style.display = 'block';
            themeText.textContent = 'Light';
            localStorage.setItem('theme', 'dark');
        }
    });
</script>
</body>
</html>
""")

# Join all parts into final HTML string
html_out = ''.join(html_parts)

# Save the HTML file
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(html_out)

print(f"Done! Exported {len(history_data)} entries to {OUTPUT_FILE}")
