# Installing the pipeline

This guide takes you from a clean machine to a working pipeline. It's written for the
person who maintains the queries (see `QUERIES.md`) and is **not** a developer. You
don't need to understand the code — you just need to get it running.

You'll use the command line (a "terminal"). Don't worry if that's unfamiliar: every
step below is a command you copy and paste. **If anything goes wrong, copy the full
error message and paste it to your AI assistant** — that's the fastest way to get
unstuck, and the assistant can almost always tell you the next step.

The instructions are for **Windows** (the pipeline runs on Windows via Power Automate).
Where macOS/Linux differ, there's a short note.

---

## 1. Install Python (3.11 or newer)

1. Go to <https://www.python.org/downloads/> and download the latest Python for Windows.
2. Run the installer. **On the first screen, tick the box "Add python.exe to PATH"**
   before clicking Install. This is the single most common thing people forget, and
   skipping it makes every later step fail with "python is not recognized".
3. Finish the install.

**Check it worked.** Open a new terminal (press the Windows key, type `powershell`,
press Enter) and run:

```powershell
python --version
```

You should see `Python 3.11.x` or higher. If you see a lower number or an error, paste
it to your AI assistant.

> **macOS/Linux:** Python is often already installed. Run `python3 --version`. If it's
> missing or too old, install from <https://www.python.org/downloads/> or your package
> manager (`brew install python` on macOS).

---

## 2. Install `uv`

`uv` is the tool that installs the pipeline's dependencies and runs it. Install it with
the official one-line command.

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS/Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After it finishes, **close the terminal and open a new one** (so it picks up the new
tool), then check:

```powershell
uv --version
```

You should see a version number. If you get "uv is not recognized", close and reopen the
terminal once more; if it still fails, paste the error to your AI assistant.

---

## 3. Install Git

Git is the tool used to download the project and later pull updates from GitHub. You
can still use the zip download below, but installing Git is recommended.

**Windows:**

1. Go to <https://git-scm.com/download/win>.
2. Download and run the installer.
3. Keep the default choices unless your IT department tells you otherwise.
4. Finish the install, then close and reopen your terminal.

**Check it worked:**

```powershell
git --version
```

You should see a version number, for example `git version 2.x.x`. If you get "git is
not recognized", close and reopen the terminal once more; if it still fails, paste the
error to your AI assistant.

> **macOS:** If Git is missing, running `git --version` usually opens Apple's installer.
> You can also install it with Homebrew: `brew install git`.
>
> **Linux:** Install Git with your package manager, for example
> `sudo apt install git` on Ubuntu/Debian.

---

## 4. Get the project onto your machine

You need the project files in a folder on your computer. Two ways:

- **Download a zip (simplest):** On the project's GitHub page, click the green **Code**
  button → **Download ZIP**. Unzip it somewhere easy to find, e.g. `Documents`.
- **Clone with Git:**
  `git clone https://github.com/theodor349/excel-data-pipeline.git`. Cloning makes it
  easier to pull future updates, but the zip is fine to start.

**Open a terminal in the project folder.** In Windows File Explorer, open the unzipped
folder (the one containing `README.md` and `run.py`), then click the address bar, type
`powershell`, and press Enter. The terminal opens already pointing at that folder.

To confirm you're in the right place, run `dir` (Windows) or `ls` (macOS/Linux) — you
should see `run.py`, `README.md`, `queries`, and `engine` in the listing.

---

## 5. Install the dependencies

From the project folder, run:

```powershell
uv sync
```

In plain language: this reads the project's list of required packages and downloads
exactly the right versions into a private folder next to the project. It doesn't touch
anything else on your computer, and you only need to run it once (and again whenever the
project's dependencies change). The first run can take a minute or two.

---

## 6. Verify the setup before touching real data

Run the test suite. This proves the pipeline installed correctly **without** needing
your real data or credentials:

```powershell
uv run pytest
```

You want to see it finish with something like `... passed` and no failures. You can also
run the query tests (fixtures only, no real sources, no output files):

```powershell
uv run python run.py --all --test-only
```

If either of these passes, the install worked. If you see failures or errors, copy the
whole output to your AI assistant.

---

## 7. Configure your data sources

The pipeline needs to know where your real files and databases are. That information
lives in `config.json`, which is **not** included in the download (it can hold passwords,
so it's deliberately kept out of the shared project).

Create your own by copying the example:

**Windows (PowerShell):**

```powershell
Copy-Item config.example.json config.json
```

**macOS/Linux:**

```bash
cp config.example.json config.json
```

Then open `config.json` in a text editor and fill in your real values — file paths to
your Excel/CSV sources and, if you use a database, its server name and login. Use
`config.example.json` as the template for what each field means. Ask your AI assistant if
a field is unclear.

> `settings.json` (the finance policy — decimal places, etc.) is already filled in and
> shared with everyone. You normally don't need to touch it.

---

## You're ready

Once `config.json` points at your real data, you can produce output files:

```powershell
uv run python run.py --all --output ./output
```

From here, see `QUERIES.md` to author and maintain queries. Whenever a command errors,
paste the full message to your AI assistant — that's the intended way to work through
problems.
