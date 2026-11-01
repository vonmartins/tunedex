# The README's demo recording. Run from the repository root, with vhs and ffmpeg:
#
#     vhs scripts/demo/demo.tape
#
# It plays in a new folder, /tmp/dj, on made-up tracks, with the tunedex of this
# checkout. The GIF goes in the README; the MP4 is for the docs and social posts.

Output docs/assets/demo.gif
Output docs/assets/demo.mp4

Require ffmpeg

Set Shell "bash"
Set FontSize 14
Set Width 1560
Set Height 580
Set Padding 24
Set Margin 28
Set MarginFill "#cba6f7"
Set WindowBar Colorful
Set BorderRadius 10
Set TypingSpeed 45ms
Set Theme "Catppuccin Mocha"
Set CursorBlink false
Set WaitTimeout 60s

Hide
Type "uv sync -q && export PATH=$PWD/.venv/bin:$PATH TUNEDEX_HOME=/tmp/dj/home && rm -rf /tmp/dj && python scripts/demo/make_library.py /tmp/dj/Music && cd /tmp/dj && clear"
Enter
Wait
Show

Type "tunedex scan Music --apply --yes"
Sleep 400ms
Enter
Wait
Sleep 2.5s

Type "tunedex fix --apply"
Sleep 400ms
Enter
Wait /Apply this plan/
Sleep 3.5s
Type "y"
Sleep 300ms
Enter
Wait
Sleep 2.5s
Hide
Type "clear"
Enter
Wait
Show

Type "tunedex dupes"
Sleep 400ms
Enter
Wait
Sleep 3.5s

Type "tunedex write-tags --apply --yes"
Sleep 400ms
Enter
Wait
Sleep 3s
Hide
Type "clear"
Enter
Wait
Show

Type "tunedex rename --apply --yes"
Sleep 400ms
Enter
Wait
Sleep 3s

Type "ls Music"
Sleep 400ms
Enter
Wait
Sleep 2.5s

Type "tunedex snapshot list"
Sleep 400ms
Enter
Wait
Sleep 5s
