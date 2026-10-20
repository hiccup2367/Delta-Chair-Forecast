# Putting this repository on GitHub

Two ways to do it. The first needs nothing but a browser. The second is faster if you already use Git.

## Option A: in the browser

1. Sign in to github.com and click the + in the top right, then "New repository".
2. Name it `delta-chair-forecast`. Choose Public or Private. Leave "Add a README", ".gitignore" and "license" all unticked, because this folder already has them.
3. Click "Create repository".
4. On the next page, click the link that says "uploading an existing file".
5. Unzip `delta-chair-forecast.zip` on your computer. Open the folder, select everything inside it (not the folder itself), and drag it onto the GitHub page.
6. Hidden files don't always come along when dragging. Check that `.github`, `.gitignore` and `.gitattributes` appear in the upload list. On a Mac, press Command, Shift and period in Finder to show hidden files; on Windows, tick "Hidden items" under the View menu in File Explorer. Drag any missing ones in separately.
7. Write a commit message such as "First version" and click "Commit changes".

GitHub's web uploader handles up to 100 files at a time, which is plenty here.

## Option B: with Git

```bash
cd delta-chair-forecast
git init
git add .
git commit -m "First version"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/delta-chair-forecast.git
git push -u origin main
```

## After the first push

- Replace `YOUR-USERNAME` in the badge at the top of `README.md` with your GitHub username so the tests badge works.
- Open the Actions tab. The tests run on Windows, macOS and Linux with Python 3.10 and 3.12. A green check means everything passed.
- Add a short description and the topics `dental`, `no-show`, `healthcare-operations`, `scikit-learn`, `privacy` under the gear icon next to About.

## Never commit real patient data

The `.gitignore` already blocks Excel files, lookup files and call lists, and the only CSV files allowed are the two fabricated samples in `data/`. Still, before every commit, look at the list of changed files. If anything that came out of a real practice appears, remove it before committing. Once something is pushed to GitHub, deleting it later doesn't remove it from the history.

## About hosting it online

Services like Streamlit Cloud or Render would put the app on a public web address. Don't do that with this app. The whole privacy design depends on the file never leaving the practice's computer. If you want people to try it without installing anything, record a short screen video of the demo using the sample practices and link it from the README instead.
