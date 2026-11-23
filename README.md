# Local Handoff MCP / AI開発エージェントのローカル引き継ぎ

Switch between Codex and Antigravity on the same PC without having to reconstruct the last session. The two clients use the same project folder and local handoff record. / 同じPCでCodexとAntigravityを交代して使うとき、前回の会話から状況を組み立て直す手間を減らします。両方が同じ作業フォルダーとローカルの引き継ぎ記録を参照します。

## Install / インストール

Download the ZIP from [GitHub Releases](https://github.com/FURUYAN1234/local-handoff-mcp/releases), extract it, run `Install.bat`, and register a project folder. For later releases, run the batch from the newly extracted ZIP. Existing work records and client registrations carry forward. / GitHub ReleasesからZIPを取得し、展開して `Install.bat` を起動し、作業フォルダーを登録します。更新時は新版ZIPのバッチを実行すると、記録と両クライアントの登録を引き継ぎます。

The installer requires Windows, WSL 2 Ubuntu, Python 3.11+ and the corresponding clients. / インストーラーにはWindows、WSL 2 Ubuntu、Python 3.11以上、および対象クライアントが必要です。

[User and MCP setup guide / 操作・MCP設定マニュアル](MANUAL.md) · [Japanese paper / 日本語論文](paper-ja.md) · [English paper / 英語論文](paper-en.md) · [Release maintenance / リリース時の文書更新](RELEASE-PROCESS.md)

[note article and Drive download / 紹介noteとDriveダウンロード](https://note.com/happy_duck780/n/n806c7bc6de94)

## Four tools / 4つのツール

| Tool / ツール | Purpose / 用途 |
| --- | --- |
| `handoff_status` | Check workspace, editing owner, saved state and Git metadata / 作業場所、編集担当、引き継ぎ記録とGitの状態を確認 |
| `handoff_recent` | Find recent records when the project is unclear / 「前回の続き」などから最近の対象を確認 |
| `handoff_checkpoint` | Record the goal, next action, checks and active jobs / 目的、次の工程、確認結果、進行中ジョブを記録 |
| `handoff_transition` | Offer, resume, recover or close a handoff / 引き渡し、再開、中断からの復帰、作業完了を記録 |

Editing ownership is enforced for MCP updates. Each client still needs to follow the shared rules when editing files. The server uses standard input and output. SQLite and the handoff notes stay on your PC. / このMCPでの記録更新には編集担当の制約がかかります。実際のファイル編集時は両クライアントが共通指示に従います。サーバーは標準入出力で通信し、SQLiteと作業記録はPC内に保管します。

## What carries over / 何を引き継げるか

Both clients use the same real project files, including the working tree and uncommitted changes. The MCP adds a shared checkpoint with the goal, work done, checks, next action and active jobs. An existing HANDOFF.md can hold longer project notes. / 両クライアントは、コミット前の変更を含む同じ作業ツリーを使います。MCPには目的、変更箇所、確認結果、次の操作、進行中の処理を残せます。詳しい背景は既存の HANDOFF.md に置けます。

Install the two clients normally and keep their own sign-ins, MCP tools and skills. Reusable instructions placed in the project can guide both clients. Each host reads its own configuration and extensions. / 両クライアントはそれぞれ通常どおりに導入し、ログイン・MCPツール・スキルを管理します。両方で使う手順は作業フォルダーにも置けます。各製品の設定や拡張機能は各クライアントが読み込みます。

## First run and update / 初回導入と更新

1. Verify that a distribution named Ubuntu is on WSL 2 and that its /usr/bin/python3 is at least 3.11. Save work and close Codex and Antigravity. / WSL 2で Ubuntu が使え、Ubuntu内の /usr/bin/python3 が3.11以上であることを確認します。両クライアントの作業を保存して閉じます。
2. Extract the complete distribution ZIP into its own folder and run Install.bat. Enter the first project root as an absolute path, for example C:\Projects\MyTool. / 配布ZIPを専用のフォルダーへすべて展開し、Install.bat を実行します。最初の作業場所は C:\Projects\MyTool のように絶対パスで入力します。
3. Reopen both clients on the same folder. Confirm the MCP named local_handoff and ask it for handoff_status. A new folder can have a null record until its first checkpoint. / 両方で同じフォルダーを開き、MCP一覧の local_handoff と handoff_status を確認します。最初のチェックポイントまで記録は空です。
4. For a later release, extract the new ZIP separately and run its Install.bat. Code lives in a versioned directory and the stable launcher selects the version after setup succeeds. The same settings and database carry over. / 次版は別フォルダーに展開し、その Install.bat を実行します。本体は版別フォルダーに置き、設定が成功してから起動先を切り替えます。設定とデータベースは引き継ぎます。

Add a project from a Windows terminal / Windowsのターミナルから作業場所を追加:

~~~bat
Install.bat --workspace "C:\Projects\AnotherTool"
~~~

## Worked example / 交代の実例

A producer is fixing a failed export test in an app. Codex has changed the code and run the normal-path test. Antigravity should run the error-path test and read the output before editing any further. / アプリの書き出しテストを直す例です。Codexで修正と正常系テストまで終え、Antigravityが異常系テストと出力の確認を受け持ちます。

| Step / 段階 | Operation / 操作 |
| --- | --- |
| Start / 作業開始 | Codex calls handoff_status on the project, then handoff_checkpoint. / Codexが対象を照合し、目的と次の操作を記録します。 |
| Save / 状況保存 | Checkpoint again with changed files, command and result, the failing case to run, and any job ID. / 変更ファイル、実行したコマンドと結果、未確認の異常例、実行中ジョブのIDを追記します。 |
| Offer / 引き渡し | Codex stops editing and calls handoff_transition with offer. / Codexの編集を止め、offer で渡します。 |
| Resume / 再開 | Antigravity inspects handoff_status, Git changes, and any running job. With current authorization it calls resume. / Antigravityが記録、Git差分、ジョブの現在状態を確認し、現在の許可で resume します。 |
| Complete / 完了 | The current owner records the result and uses complete. / 現担当が結果を保存し、complete で閉じます。 |

A useful checkpoint includes enough to verify claims without the transcript. / 会話を読み返さなくても確認できるよう、チェックポイントには次のように書きます。

~~~json
{
  "workspace": "C:/Projects/MyTool",
  "goal": "Fix handling of failed exports",
  "completed": "Updated export validation; successful exports still pass",
  "checks": "Normal case passed; empty input still needs a test",
  "next_step": "Run the empty-input regression and inspect the returned error",
  "active_jobs": "No running jobs"
}
~~~

If a quota or crash interrupts the first client, inspect the same folder and running jobs. When the user wants to switch and the first client has stopped editing, use recover with previous_stopped set to true, record the evidence at the next checkpoint, and continue. Without stopping the first editor or verifying a running job, leave ownership where it is. / クレジット切れや異常終了では、同じフォルダーと実行中ジョブを確認します。ユーザーが交代を希望し、前任が編集を止めたと確認できたら previous_stopped を true にして recover し、その確認根拠を次のチェックポイントへ記録します。前任の停止やジョブの状態が分かるまでは担当を動かしません。

If the user says only “continue,” handoff_recent shows recent unfinished records. Match the project to the current request before resuming. / 「続き」だけなら handoff_recent で最近の未完了案件を確認し、今回の依頼に当てはまる作業だけを再開します。

## Data and troubleshooting / データと困ったとき

| Symptom / 症状 | Check / 確認 |
| --- | --- |
| No local_handoff in the tool list / MCP一覧に表示されない | Reopen the clients and check that Ubuntu and its system Python run. Read the client MCP error. / 両方を開き直し、UbuntuとシステムPythonが起動するか、MCPの接続エラーを確認します。 |
| A different local_handoff entry already exists / 同名で別の登録がある | The batch stops before replacing that registration. Check the path and migrate the existing setup deliberately. / バッチは登録の上書き前に停止します。先に登録内容とデータの保管先を確認します。 |
| Workspace rejected / 作業場所が対象外 | Register the existing project's absolute path with --workspace. Avoid registering an entire home directory. / 実在する作業フォルダーを絶対パスで登録します。対象はプロジェクト単位に絞ります。 |
| Other client owns editing / 相手が担当中 | Wait for the owner to offer the project, or confirm it has stopped before recovery. / 相手が作業を止めて引き渡すのを待つか、停止確認のうえで復帰します。 |
| Git status unavailable / Gitの状態が確認できない | Check the actual files and Git from the appropriate host. The checkpoint still reports handoff state. / 実際のファイルと対象環境のGitを確認します。引き継ぎ記録そのものは参照できます。 |

Storage lives inside Ubuntu at ~/.local/share/local-handoff-mcp. A backup contains settings and SQLite data, including workspace paths and text entered in checkpoints. Keep it private, and close both clients before copying both together. / 保存場所はUbuntu内の ~/.local/share/local-handoff-mcp。設定とSQLiteには作業フォルダーや入力した進捗が含まれます。バックアップは両クライアントを閉じてからまとめてコピーし、非公開で保管します。

The server queries Git branch, HEAD and file-status summaries. A status fingerprint detects changes in the Git status listing. It is possible to edit an already-modified file while that listing stays the same. Always inspect the actual diff or artifact when switching. / Gitではブランチ・HEAD・変更の集計を参照します。状態の指紋はGitの状態一覧の変化を検出します。変更済みファイルをさらに直しても一覧が同じ場合があるため、交代時は実際の差分や成果物も確認します。

Local Handoff MCP uses no cloud inference by itself. Checkpoints carry no publication approval or billing permission. Use the current instruction for external actions and inspect a running job before starting another one. / Local Handoff MCP自体はクラウド推論を使いません。チェックポイントで公開や課金の許可は更新されません。外部操作は今回の指示を確認し、実行中ジョブを調べてから次の操作を決めます。

## Development / 開発

```sh
/usr/bin/python3 -B -m unittest -v
/usr/bin/python3 -B check_release_docs.py
/usr/bin/python3 -B build_package.py /tmp/local-handoff-release
```

MIT license / MITライセンス

## Related apps and workflows / 関連アプリ・ワークフロー

[AI Manga Creative Suite / AIまんが制作エコシステム](https://note.com/happy_duck780/n/nbdf826604ce7)

- Super FURU AI 4-koma System · [GitHub](https://github.com/FURUYAN1234/nano-banana-pro) · [Guide / 解説](https://note.com/happy_duck780/n/ndf063558c1f5)
- AI Image Bridge · [GitHub](https://github.com/FURUYAN1234/ai-image-bridge) · [Guide / 解説](https://note.com/happy_duck780/n/n6747a089fce7)
- AI Story Maker · [GitHub](https://github.com/FURUYAN1234/story-maker) · [Guide / 解説](https://note.com/happy_duck780/n/nd3d972922868)
- AI Character Sheet Maker · [GitHub](https://github.com/FURUYAN1234/character-sheet-maker) · [Guide / 解説](https://note.com/happy_duck780/n/neccbebd7d957)
- AI Comic Translation Tool · [GitHub](https://github.com/FURUYAN1234/comic-translation) · [Guide / 解説](https://note.com/happy_duck780/n/ne462dfc55ec8)
- PanoForge / 360° AI Panorama Generator · [GitHub](https://github.com/FURUYAN1234/panoforge) · [Guide / 解説](https://note.com/happy_duck780/n/nb53b121fef88)
- AI Voice Comic Maker · [GitHub](https://github.com/FURUYAN1234/ai-voice-comic-maker) · [Guide / 解説](https://note.com/happy_duck780/n/ndc6533c1512f)
- Monogatari Buzz Maker / 物語バズメーカー · [GitHub](https://github.com/FURUYAN1234/viral-radar) · [Guide / 解説](https://note.com/happy_duck780/n/ncc593101d77f)
- Narrated Video Maker / ナレーション動画メーカー · [GitHub](https://github.com/FURUYAN1234/gemini-narration-studio) · [Guide / 解説](https://note.com/happy_duck780/n/n97d49c1c98b1)
- MiniMax H3 Video / T2V・I2V・Ref2V · [GitHub](https://github.com/FURUYAN1234/comfyui-h3-workflows) · [Guide / 解説](https://note.com/happy_duck780/n/n15e732b3147b)
- MiniMax H3 MV / 完成曲からミュージックビデオ · [GitHub](https://github.com/FURUYAN1234/comfyui-h3-workflows) · [Guide / 解説](https://note.com/happy_duck780/n/ne8a84cb6db37)
- KomaOrbit / 一枚絵から3Dで構図を探す · [GitHub](https://github.com/FURUYAN1234/comfyui-h3-workflows) · [Guide / 解説](https://note.com/happy_duck780/n/n3f68482d5edd)
- 長尺動画AnimeSharpアップスケーラー · [GitHub](https://github.com/FURUYAN1234/comfyui-long-video-upscaler) · [Guide / 解説](https://note.com/happy_duck780/n/n0f190160e307)
- 日本語おまかせ作曲 / LM Studio × YuE2 · [GitHub](https://github.com/FURUYAN1234/ComfyUI-YuE2-Japanese) · [Guide / 解説](https://note.com/happy_duck780/n/n57df44cf7fd2)
- 日本語おまかせナレーション / AI相談・手動編集 · [GitHub](https://github.com/FURUYAN1234/ComfyUI-Local-Narration-Japanese) · [Guide / 解説](https://note.com/happy_duck780/n/nda7ed302d544)
- MangaScreen JP / 日本語操作・原寸出力 · [GitHub](https://github.com/FURUYAN1234/ComfyUI-MangaScreen-JP) · [Guide / 解説](https://note.com/happy_duck780/n/n5c89a250fb82)
- Codex Usage / Codex 残量 · [GitHub](https://github.com/FURUYAN1234/codex-usage-overlay)
