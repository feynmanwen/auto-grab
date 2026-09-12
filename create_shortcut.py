import os
import subprocess

def create_desktop_shortcut():
    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    project_dir = os.path.dirname(os.path.abspath(__file__))
    target_bat = os.path.join(project_dir, 'run.bat')
    shortcut_path = os.path.join(desktop, 'auto-grab 自動文字點選.lnk')

    vbs_path = os.path.join(project_dir, '_make_shortcut.vbs')
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
Set Shortcut = WshShell.CreateShortcut("{shortcut_path}")
Shortcut.TargetPath = "{target_bat}"
Shortcut.WorkingDirectory = "{project_dir}"
Shortcut.Description = "auto-grab Screen OCR AutoClicker"
Shortcut.IconLocation = "shell32.dll,22"
Shortcut.Save
'''
    # VBScript requires UTF-16LE with BOM to properly parse non-ASCII paths
    with open(vbs_path, 'w', encoding='utf-16') as f:
        f.write(vbs_content)

    subprocess.run(['cscript.exe', '//Nologo', vbs_path], check=True)
    if os.path.exists(vbs_path):
        os.remove(vbs_path)
    print(f"成功在桌面建立捷徑: {shortcut_path}")

if __name__ == '__main__':
    create_desktop_shortcut()
