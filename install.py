# -*- coding: utf-8 -*-
"""bsv-gongmun-year-update installer (install.cmd runs this with the Python it found).

- pip-installs requirements.txt (kiwipiepy is optional: a failure only prints a note)
- copies the skill folder to the Claude Code, Codex and Antigravity user skill folders:
    %USERPROFILE%\\.claude\\skills\\bsv-gongmun-year-update
    %USERPROFILE%\\.codex\\skills\\bsv-gongmun-year-update
    %USERPROFILE%\\.gemini\\config\\skills\\bsv-gongmun-year-update   (Antigravity App and CLI global skills)
- safe to run again: its own earlier install (marked with .bsv-install.json) is replaced;
  a folder it did not make is moved to %USERPROFILE%\\.bsv-gongmun-year-update\\backup\\ first, never deleted
- copies the empty school-rule template to %USERPROFILE%\\.bsv-gongmun-year-update\\표시규칙_예시.json if absent
Nothing is sent anywhere except the pip downloads.
"""
import os, sys, json, shutil, subprocess, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "bsv-gongmun-year-update"
MARK = ".bsv-install.json"
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MSG = json.load(open(os.path.join(HERE, "install_messages.json"), encoding="utf-8"))


def say(key, **kw):
    s = MSG[key]
    for k, v in kw.items():
        s = s.replace("{" + k + "}", str(v))
    print(s, flush=True)


def targets(home):
    return [os.path.join(home, ".claude", "skills", NAME),
            os.path.join(home, ".codex", "skills", NAME),
            os.path.join(home, ".gemini", "config", "skills", NAME)]


def requirements():
    core, optional = [], []
    with open(os.path.join(HERE, "requirements.txt"), encoding="utf-8") as f:
        for line in f:
            spec, _, note = line.partition("#")
            spec = spec.strip()
            if spec:
                (optional if "optional" in note else core).append(spec)
    return core, optional


def pip(pkgs):
    base = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--quiet"]
    if subprocess.run(base + pkgs).returncode == 0:
        return True
    return subprocess.run(base + ["--user"] + pkgs).returncode == 0   # fall back to the user site when site-packages is not writable


def place(src, dst, home, stamp):
    """Copy the skill to dst. Replace our own earlier install; move any other folder to the backup folder."""
    if os.path.exists(dst):
        if os.path.isfile(os.path.join(dst, MARK)):
            shutil.rmtree(dst)
        else:
            bk = os.path.join(home, ".bsv-gongmun-year-update", "backup", stamp, os.path.basename(os.path.dirname(os.path.dirname(dst))) + "-" + NAME)
            os.makedirs(os.path.dirname(bk), exist_ok=True)
            shutil.move(dst, bk)
            say("i.backup", PATH=bk)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".installing"
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    shutil.copytree(src, tmp, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    with open(os.path.join(tmp, "tools", "python_path.txt"), "w", encoding="utf-8") as f:
        f.write(sys.executable + "\n")
    with open(os.path.join(tmp, MARK), "w", encoding="utf-8") as f:
        json.dump({"name": NAME, "installed_at": stamp, "source": "https://github.com/rheps/bsv-gongmun-year-update",
                   "python": sys.executable}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, dst)
    say("i.installed", PATH=dst)


def main():
    say("i.start")
    if sys.version_info < (3, 10):
        say("i.old_python")
        return 1
    home = os.path.expanduser("~")
    core, optional = requirements()
    say("i.pip")
    if not pip(core):
        say("i.pip_fail")
        return 1
    for p in optional:
        if not pip([p]):
            say("i.kiwi_fail")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    src = os.path.join(HERE, NAME)
    for dst in targets(home):
        place(src, dst, home, stamp)
    cfg = os.path.join(home, ".bsv-gongmun-year-update")
    os.makedirs(cfg, exist_ok=True)
    ex = os.path.join(cfg, "표시규칙_예시.json")
    if not os.path.exists(ex):
        shutil.copy2(os.path.join(src, "tools", "표시규칙_예시.json"), ex)
    sys.path.insert(0, os.path.join(src, "tools"))
    import office
    if not office.hwp_available():
        say("i.hwp_missing")
    if not office.soffice():
        say("i.lo_missing")
    say("i.done")
    say("i.restart")
    return 0


if __name__ == "__main__":
    sys.exit(main())
