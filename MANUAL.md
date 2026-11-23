# User and MCP setup guide / 操作・MCP設定マニュアル

The dashboard's MCP setup links open instructions for each client. Use the controls in the dashboard or the client to install, register or sign in. / 管理画面の「MCP手順を見る」は、接続先ごとの手順を開きます。導入・登録・認証は管理画面のボタンや各アプリから行います。

## Prerequisites / 必要環境

Windows with WSL 2, a distribution named Ubuntu, Python 3.11 or later at `/usr/bin/python3` inside Ubuntu, and Codex and Antigravity clients running under the same Windows account. Git is optional for non-Git folders. Git for Windows is recognized in its standard installation directory. / Windows、WSL 2のUbuntu、Ubuntu内の `/usr/bin/python3`（3.11以上）、同じWindowsユーザーで使うCodexとAntigravityが必要です。Gitを使わないフォルダーでも作業は引き継げます。Git for Windowsは標準の場所にある場合に自動認識します。

The handoff server connects over local standard input and output. It requires no model API key or external account. Codex and Antigravity retain their normal sign-in and quota requirements. / 引き継ぎMCPはローカルの標準入出力で接続します。MCP自体にモデルAPIキーや外部アカウントは不要です。CodexとAntigravityは通常どおりのログイン・利用枠を使います。

## Install or update / 導入・更新

1. Close both clients after saving work. Extract the entire ZIP to a new folder and run `Install.bat`. At first launch, enter the project's absolute path. / 作業を保存して両クライアントを閉じます。ZIPを新しいフォルダーにすべて展開し、`Install.bat` を実行します。初回はプロジェクトの絶対パスを入力します。
2. Reopen the clients. Confirm `local_handoff` under the client MCP list and ask the client to run `handoff_status` on your project. / 両方を開き直し、MCP一覧の `local_handoff` と、対象フォルダーでの `handoff_status` を確認します。
3. For a new version, download and extract its ZIP separately and run the same batch. The installed launcher switches versions and reuses the database, registered roots and client registrations. / 新版は別フォルダーへ展開し、同じバッチを実行します。起動先の版を切り替え、データベース・作業場所・両クライアントの登録を引き継ぎます。

Add another project from a Windows terminal / Windowsのターミナルから作業場所を追加:

```bat
Install.bat --workspace "C:\Projects\Example"
```

Client registration is stored in `%USERPROFILE%\.codex\config.toml` and `%USERPROFILE%\.gemini\config\mcp_config.json`. If either client already has a different `local_handoff` entry, installation stops so you can review the existing setup. Existing custom registrations and hooks can be managed in each client. / 両クライアントへの登録先は上記の設定ファイルです。異なる `local_handoff` 登録が見つかったら、既存構成を確認できるようにインストールを止めます。独自設定やフックは各クライアントで管理します。

## Handoff / 作業を交代する

- **Start** — Open the same folder and check `handoff_status`, then use `handoff_checkpoint` before editing. / **開始** — 同じフォルダーを開き、状態を確認してからチェックポイントを記録します。
- **Switch** — The first client checkpoints and calls `offer`. The second checks files, jobs and current permission before `resume`. / **交代** — 渡す側は現状を保存して `offer`、受ける側は現物と実行中の処理・許可を確認して `resume` します。
- **Recover** — If work stopped unexpectedly, verify the previous client and jobs have stopped, then record the evidence with `recover` using current authorization. / **復帰** — 途中で止まったときは前任とジョブの状態を確認し、現在の許可と確認根拠をもって `recover` します。
- **Close** — Call `complete` once the requested work is finished. / **完了** — 依頼範囲が完了したら `complete` を記録します。

The installer adds standing instructions. They help each assistant remember to record work. Editing outside those instructions remains possible, so check the actual workspace and running jobs at the switch. / インストーラーは共通指示を追加し、各アシスタントが作業記録を忘れにくくします。ファイルの実際の編集とジョブの状態は交代時に確認してください。

## Dashboard / 管理画面

After Install.bat, run Dashboard.bat. Run the same batch again to reopen the dashboard after closing the browser tab. It reuses the running local server, or starts it again when needed. Close the first dashboard terminal to stop the server. Use Refresh to scan for clients again. Open a project by its name to see its written notes and recorded observations. / Install.bat の実行後、Dashboard.bat を開きます。ブラウザーのタブを閉じても、同じバッチから管理画面を開き直せます。起動中なら同じサーバーを使い、停止中なら新しく起動します。最初に起動した端末を閉じるとサーバーが止まります。「更新」でAIを再検出し、案件名を選ぶと引き継ぎの詳細と観測履歴を表示します。

Detection covers standard Windows installations and commands on PATH for Codex, Antigravity, Claude Code, OpenCode and Strata. The dashboard also checks the standard local endpoints for Ollama (11434) and LM Studio (1234). Registration indicates the client has an enabled local_handoff entry. Confirm a live connection in that client's MCP list. When sign-in status is unavailable, the dashboard says so. / Codex、Antigravity、Claude Code、OpenCodeの標準的な導入先と、PATH上の対応コマンドを検出します。StrataはWSL内の対応環境を検出します。Ollama（11434）とLM Studio（1234）は標準ポートの応答を確認します。WindowsのLM Studioが起動している場合は、公式CLIで標準以外の設定・待受ポートも確認します。MCP登録表示は、有効な local_handoff 設定があることを示します。実際の接続はクライアントのMCP一覧で確認してください。認証状況を取得できない製品や版では未確認と表示します。

## Codex setup / Codexの設定

Check the Codex row in the Local Handoff MCP dashboard for a registration. If a registration is present, check for `local_handoff` in Codex's MCP settings. If you are setting it up for the first time, open the full manual and follow Install or update. / 管理画面のCodex欄でMCP登録の表示を確認します。登録済みなら、CodexのMCP設定で `local_handoff` を確認します。初回のセットアップは「マニュアル全体」の「導入・更新」を参照してください。

## Antigravity setup / Antigravityの設定

Check the Antigravity row in the dashboard. If MCP is registered, check that `local_handoff` appears and is enabled in Antigravity's MCP settings. For a first-time setup, open the full manual and follow Install or update. If sign-in is needed, choose Open Antigravity and sign in inside the app. / 管理画面のAntigravity欄でMCP登録の表示を確認します。登録済みなら、AntigravityのMCP設定で `local_handoff` が表示され、有効になっているか確認します。初回のセットアップは「マニュアル全体」の「導入・更新」を参照してください。ログインが必要なら「Antigravityを開く」を選び、アプリ内で認証します。

## Claude Code setup / Claude Codeの設定

After installing Claude Code, select Register MCP in the dashboard. It uses Claude Code's user-scope registration command. Reopen Claude Code and use /mcp to confirm the connection. If Claude Code supports the dedicated login command, use Open authentication page. Older versions open Claude Code in a terminal. First-time users select a theme and login method. In an already configured terminal, enter /login. / Claude Codeを導入し、管理画面で「MCPを登録」を選びます。Claude Codeのユーザー設定へ登録されます。Claude Codeを開き直し、/mcp で接続を確認します。専用ログインコマンドに対応した版では「認証ページを開く」を選びます。旧版はClaude Codeの端末を開きます。初回はテーマとログイン方法を選び、設定済みの端末では /login を入力すると、公式ページがブラウザーに開きます。

Before editing, call handoff_status with the absolute workspace. Save a checkpoint at the start, after a milestone and before handing off. Use recipient when offering to Claude Code or OpenCode, and previous_owner when recovering from either. / 編集前に対象を handoff_status で照合します。開始時、工程の区切り、交代前にチェックポイントを残します。Claude CodeやOpenCodeを宛先にするときは recipient を、両者が前任の復帰では previous_owner を指定します。

```json
{"workspace":"C:/Projects/Example","action":"offer","recipient":"claude-code"}
```

## OpenCode and local models / OpenCodeとローカルモデル

If OpenCode is missing and your WSL Ubuntu is x64, choose Install CLI in the OpenCode row. The dashboard downloads a pinned official binary, verifies the npm package integrity and installs it under Local Handoff MCP's WSL directory. Use Refresh to see the result. For the desktop app, choose the official installation guide. / OpenCodeが未検出でWSL Ubuntuがx64の場合は、OpenCode欄の「OpenCode CLIをインストール」を選びます。公式の固定版を取得し、npm配布物の整合性を確認してからLocal Handoff MCPのWSL専用フォルダーに入れます。「更新」で結果を確認できます。デスクトップアプリは「公式インストール手順」から入手します。

Open the managed CLI from Ubuntu with `~/.local/share/local-handoff-mcp/bin/opencode`. Follow the setup in OpenCode if you need to connect an account or model. / 専用CLIはUbuntuで `~/.local/share/local-handoff-mcp/bin/opencode` を実行して起動します。アカウントやモデルの接続が必要ならOpenCode側で設定します。

Use the installed OpenCode version's local MCP configuration. For a Windows OpenCode client, set its local server command array to the following example. Replace YOUR_WSL_USER with your Ubuntu username. For OpenCode running inside Ubuntu, use the same arguments from /usr/bin/python3 onward. / OpenCodeの版に合うローカルMCP設定を使います。Windows版では次のコマンド配列を指定し、YOUR_WSL_USER をUbuntuのユーザー名に置き換えます。Ubuntu内のOpenCodeでは /usr/bin/python3 以降を同じ順で指定します。

```json
["wsl.exe","-d","Ubuntu","--exec","/usr/bin/python3","-B","/home/YOUR_WSL_USER/.local/share/local-handoff-mcp/launch.py","--host","opencode","serve"]
```

Use the name local_handoff and type local. OpenCode v1 places the entry under mcp; v2 places it under mcp.servers. Confirm it with opencode mcp list. Select a local model that supports tool calls. Plain chat or inference software needs a client that can call MCP tools. / 名前は local_handoff、type は local を指定します。OpenCode v1 は mcp 配下、v2 は mcp.servers 配下に登録します。opencode mcp list で接続を確認し、ツール呼び出しに対応したローカルモデルを選択します。

[OpenCode MCP](https://opencode.ai/docs/mcp-servers/) · [Ollama setup for OpenCode](https://docs.ollama.com/integrations/opencode) · [LM Studio local API](https://lmstudio.ai/docs/developer/core/server)

## Strata in WSL / WSL版Strataの設定

In Strata, go to Settings → Tools, add a custom tool server named Local Handoff, and specify the program and arguments below. Replace YOUR_WSL_USER with your Ubuntu username and enter one argument per line. For the required description use “Read and update local project handoff records.” Choose the existing model in Strata, and ask it to run handoff_status before editing. For handoff to Strata use recipient strata. / Strataの Settings → Tools で「Local Handoff」というツールサーバーを追加します。プログラムは次の1行目、引数は2行目以降をそれぞれ1行ずつ入力してください。説明欄には「ローカルの作業引き継ぎ記録を読み書きする」と入力し、YOUR_WSL_USER はUbuntuのユーザー名に置き換えます。Strataで使うモデルを選び、編集前に handoff_status で照合します。引き渡すときの recipient は strata です。

```
/usr/bin/python3
-B
/home/YOUR_WSL_USER/.local/share/local-handoff-mcp/launch.py
--host
strata
serve
```

## Scheduled observations / 定期観測

Run Autosave.bat after installation. To run it periodically, configure Windows Task Scheduler for your own account and point it at the extracted Autosave.bat. One run saves the first observation, then saves only changes to observable workspace metadata. Only active projects are sampled. / 導入後に Autosave.bat を実行できます。定期実行する場合はWindowsタスク スケジューラで自分のアカウントを使い、展開した Autosave.bat を指定します。初回と観測情報に変化があるときに保存します。対象は担当ありの案件です。

History retains up to 100 written checkpoints and 100 automated observations per workspace. Automated observations do not back up file contents, infer work progress or confirm job status. Keep recording intent, verification and job observations with handoff_checkpoint. / 作業フォルダーごとにチェックポイントと自動観測を各100件まで保持します。自動観測の対象はGitメタデータ等です。ファイル本体のバックアップ、進捗の推測、ジョブの稼働確認は別途行い、目的・検証結果・ジョブの確認結果は handoff_checkpoint に記録します。

## Local data / ローカルデータ

The data directory is `~/.local/share/local-handoff-mcp` inside Ubuntu. To back up or manually migrate an installation, close both clients first and preserve `settings.json` and the SQLite database together. It can contain project paths and work notes. Treat both as private. / データの保管場所はUbuntu内の上記フォルダーです。バックアップや移行は両クライアントを閉じたうえで、`settings.json` とSQLiteデータベースを一緒に保管します。作業場所や進捗が含まれるため、非公開で保管してください。
