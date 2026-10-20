# Setting up Chair Forecast

This is for whoever installs the app at the practice, usually the office manager. Plan on fifteen minutes the first time. You don't need to be technical.

## What you need

- A Windows 10 or 11 PC, or a Mac running macOS 12 or newer. The front desk computer is fine.
- Python 3.10 or newer. It's free.
- An internet connection for the first launch only.

## 1. Install Python (skip if it's already there)

**Windows.** Go to python.org/downloads and download the latest Python 3 installer. On the first screen of the installer, tick "Add python.exe to PATH" before clicking Install. That checkbox is the step people most often miss.

**Mac.** Go to python.org/downloads and install the latest Python 3 package. When it finishes, a Finder window opens; double-click "Install Certificates.command" in it.

If your IT provider manages the office computers, send them this page. Python is a standard, widely used program and they will know it.

## 2. Get the app folder

Download the repository as a ZIP from GitHub (green "Code" button, then "Download ZIP") or take the folder from whoever sent it to you. Unzip it somewhere easy to find, such as Documents.

Don't put it in a folder that syncs to the cloud (OneDrive Desktop, iCloud Documents, Dropbox). The app never saves patient data there, but the private lookup file you might download later should stay off synced folders too, and it's simpler to keep everything in one local place.

## 3. Start it

**Windows.** Open the folder and double-click `start-windows.bat`. A black window appears. The first time, it spends a few minutes setting things up; you'll see lines scroll by. Then your web browser opens on the app.

If Windows shows a blue "Windows protected your PC" box, click "More info" and then "Run anyway". That warning appears for any script that wasn't downloaded from the Microsoft Store.

**Mac.** Open the folder, right-click `start-mac.command` and choose Open. Confirm when macOS asks. You only need the right-click the first time; after that a double-click works. If macOS says the file can't be opened because it isn't executable, open Terminal, type `chmod +x ` (with a space), drag the file into the Terminal window, and press Return.

The app opens at `http://127.0.0.1:8765`. The address starts with 127.0.0.1, which means "this computer". Nothing else on the network, and nothing on the internet, can reach it.

## 4. Check it works

On the start screen, click "Plan the next two weeks". That loads a made-up practice. You should see the turning triangle for a second or two, then a plan. If you get that far, the setup is done.

## Every day after that

Double-click the same start file. It opens in a few seconds and doesn't need the internet. Keep the black window (or Terminal window) open while you use the app. Close it to stop the app; closing it also wipes anything that was loaded.

A desktop shortcut helps. On Windows, right-click `start-windows.bat`, choose "Show more options", then "Send to" and "Desktop (create shortcut)". On a Mac, drag `start-mac.command` to the right-hand side of the Dock.

## Updating

Download the new version, unzip it next to the old one, and copy the `.venv` folder across if you want to skip the first-time setup. Or just run the new start file and let it set itself up again.

## Removing it

Delete the folder. The app doesn't install anything elsewhere on the computer. Python stays installed; remove it from Settings (Windows) or by deleting it from Applications (Mac) if nothing else uses it.

## If setup fails

| What you see | What to do |
| --- | --- |
| "Python 3.10 or newer is needed and was not found" | Install Python (step 1). On Windows, make sure "Add python.exe to PATH" was ticked. Reinstalling with the box ticked fixes it. |
| "Setup did not finish" | The first launch couldn't download its parts. Check the internet connection and run the start file again. Office firewalls sometimes block this; ask IT to allow pypi.org and files.pythonhosted.org for the first setup. |
| The browser didn't open | Open any browser and go to `http://127.0.0.1:8765`. If that port was busy, the black window prints the address it used instead. |
| "This site can't be reached" later on | The black window was closed. Start the app again. |
| Something else | Delete the `.venv` folder inside the app folder and run the start file again. That redoes the first-time setup from scratch. |
