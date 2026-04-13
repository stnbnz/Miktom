import os

base_dir = r"d:\Project\miktom\web_monitor\dashboard\templates\dashboard"
index_path = os.path.join(base_dir, "index.html")

with open(index_path, "r", encoding="utf-8") as f:
    html = f.read()

# We need to split html:
# 1. Everything before <div class="container"> inside .app-container
# 2. Everything inside <div class="container"> (up to its closing tag) -> block content
# 3. Everything after </div> of app-container.

split1 = html.split('<div class="container">')
head_and_sidebar = split1[0]

# Now let's find the closing </div> of <div class="app-container">
# Since we know the layout, container is closed, then app-container is closed.
# There are two </div></div>.
split2 = split1[1].split('</div>\n    </div>')
container_content = split2[0].strip()

# Now modals and scripts
split_after_container = '    </div>\n    </div>' + split2[1]
# We want to keep the error-toast and action-toast in base.html
# After <div class="action-toast" id="action-toast"> ... </div>
split3 = split_after_container.split('<div id="reboot-modal"')
toasts_part = split3[0].replace('    </div>\n    </div>\n\n', '')
modals_and_scripts = '<div id="reboot-modal"' + split3[1]
split4 = modals_and_scripts.split('<script>')
modals_part = split4[0].strip()
scripts_part = '<script>\n' + split4[1].replace('</body>\n</html>', '').strip()

# Create base.html
base_html = head_and_sidebar + '''<div class="container">
            {% block content %}{% endblock %}
        </div>
    </div>

''' + toasts_part + '''

    {% block modals %}{% endblock %}

    <script>
        function showToast(message, type="success") {
            const toast = document.getElementById('action-toast');
            const icon = document.getElementById('toast-icon');
            toast.className = 'action-toast ' + type + ' show';
            document.getElementById('action-msg').innerText = message;
            
            if(type === 'success') {
                icon.innerHTML = '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline>';
            } else {
                icon.innerHTML = '<circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line>';
            }
            
            setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        }
    </script>
    
    <style>
        .sidebar-item.active {
            border-left-color: var(--accent-primary);
            background: linear-gradient(90deg, rgba(112, 0, 255, 0.1), transparent);
        }
    </style>
    
    {% block scripts %}{% endblock %}
</body>
</html>
'''

# We also need to fix active states in base.html so we use django urls
# We will just replace hrefs with {% url %} if possible, but actually we can just pass an active class or let js handle it.
# Let's fix the links:
base_html = base_html.replace('href="/" class="sidebar-item active"', 'href="/" class="sidebar-item {% if request.resolver_match.url_name == \'index\' %}active{% endif %}"')
base_html = base_html.replace('href="/voucher/" class="sidebar-item"', 'href="/voucher/" class="sidebar-item {% if request.resolver_match.url_name == \'voucher_page\' %}active{% endif %}"')
base_html = base_html.replace('href="#" class="sidebar-item"\n                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>\n                Active Users\n            </a>', 'href="/active-users/" class="sidebar-item {% if request.resolver_match.url_name == \'active_users\' %}active{% endif %}">\n                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>\n                Active Users\n            </a>')
base_html = base_html.replace('href="#" class="sidebar-item"\n                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>\n                Settings\n            </a>', 'href="/settings/" class="sidebar-item {% if request.resolver_match.url_name == \'settings_page\' %}active{% endif %}">\n                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>\n                Settings\n            </a>')


# Reconstruct index.html
new_index_html = '{% extends "dashboard/base.html" %}\n\n{% block content %}\n' + container_content + '\n{% endblock %}\n\n{% block modals %}\n' + modals_part + '\n{% endblock %}\n\n{% block scripts %}\n' + scripts_part + '\n{% endblock %}\n'

with open(os.path.join(base_dir, "base.html"), "w", encoding="utf-8") as f:
    f.write(base_html)

with open(index_path, "w", encoding="utf-8") as f:
    f.write(new_index_html)

print("done writing base.html and index.html")
