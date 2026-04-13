import os

def patch_index():
    index_path = r"d:\Project\miktom\web_monitor\dashboard\templates\dashboard\index.html"
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Find where header-info starts, this is the first item inside container
    start_idx = html.find('<div class="header-info">')
    
    # We also need navbar content
    nav_start = html.find('<div style="display:flex; gap:15px; align-items:center;">')
    nav_end = html.find('</nav>')
    nav_content = html[nav_start + 59:nav_end].strip()[:-6].strip()

    # End of container
    # Since we know the modals start with <div id="reboot-modal", the container ends before that
    reboot_modal_idx = html.find('<div id="reboot-modal"')
    error_toast_idx = html.find('<div class="error-toast"')
    container_end = html.rfind('</div>', 0, error_toast_idx - 1)
    container_end = html.rfind('</div>', 0, container_end - 1)
    
    content_html = html[start_idx:container_end].strip()
    
    # Modals
    script_idx = html.find('<script>')
    modals_html = html[reboot_modal_idx:script_idx].strip()
    
    # Scripts
    script_content = html[script_idx:html.find('</body>')].replace('<script>', '').replace('</script>', '').strip()
    
    # Remove the generic showToast from script_content if we put it in base
    
    new_html = f"""{{% extends "dashboard/base.html" %}}

{{% block navbar_right %}}
{nav_content}
{{% endblock %}}

{{% block content %}}
{content_html}
{{% endblock %}}

{{% block modals %}}
{modals_html}
{{% endblock %}}

{{% block scripts %}}
<script>
{script_content}
</script>
{{% endblock %}}
"""
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(new_html)

def patch_voucher():
    voucher_path = r"d:\Project\miktom\web_monitor\dashboard\templates\dashboard\voucher.html"
    with open(voucher_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Similar patching
    start_idx = html.find('<div class="header-info">')
    
    nav_start = html.find('<div style="display:flex; gap:15px; align-items:center;">')
    nav_end = html.find('</nav>')
    nav_content = html[nav_start + 59:nav_end].strip()[:-6].strip()

    error_toast_idx = html.find('<div class="error-toast"')
    if error_toast_idx == -1:
        error_toast_idx = html.find('<script>')
    
    # container_end is roughly before error-toast
    container_end_search = html.rfind('</div>', 0, error_toast_idx)
    # usually 2 nested divs closing app-container and container
    container_end = container_end_search
    
    # find where to actually cut
    content_html = html[start_idx:error_toast_idx].strip()
    # Let's clean up closing divs at the end of content_html
    while content_html.endswith('</div>'):
        content_html = content_html[:-6].strip()
        
    script_idx = html.find('<script>')
    if script_idx != -1:
        script_content = html[script_idx:html.find('</body>')].replace('<script>', '').replace('</script>', '').strip()
    else:
        script_content = ""
        
    new_html = f"""{{% extends "dashboard/base.html" %}}

{{% block title %}}Manajemen Voucher{{% endblock %}}

{{% block loader_text %}}Loading Data...{{% endblock %}}

{{% block navbar_right %}}
{nav_content}
{{% endblock %}}

{{% block content %}}
{content_html}
{{% endblock %}}

{{% block scripts %}}
<script>
{script_content}
</script>
{{% endblock %}}
"""
    with open(voucher_path, "w", encoding="utf-8") as f:
        f.write(new_html)

patch_index()
patch_voucher()
print("done")
