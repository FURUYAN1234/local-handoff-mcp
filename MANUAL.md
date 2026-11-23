# User and MCP setup guide / 操作・MCP設定マニュアル

The dashboard's MCP setup links open instructions for each client. Use the controls in the dashboard or the client to install, register or sign in. / 管理画面の「MCP手順を見る」は、接続先ごとの手順を開きます。導入・登録・認証は管理画面のボタンや各アプリから行います。

## Prerequisites / 必要環境

Windows with WSL 2, a distribution named Ubuntu, Python 3.11 or later at `/usr/bin/python3` inside Ubuntu, and Codex and Antigravity clients running under the same Windows account. Git is optional for non-Git folders. Git for Windows is recognized in its standard installation directory. / Windows、WSL 2のUbuntu、Ubuntu内の `/usr/bin/python3`（3.11以上）、同じWindowsユーザーで使うCodexとAntigravityが必要です。Gitを使わないフォルダーでも作業は引き継げます。Git for Windowsは標準の場所にある場合に自動認識します。

The handoff server connects over local standard input and output. It requires no model API key or external account. Codex and Antigravity retain their normal sign-in and quota requirements. / 引き継ぎMCPはローカルの標準入出力で接続します。MCP自体にモデルAPIキーや外部アカウントは不要です。CodexとAntigravityは通常どおりのログイン・利用枠を使います。

## Install or update / 導入・更新

1. Close both clients after saving work. Extract the entire ZIP to a new folder and run `Install.bat`. At first launch, enter the project's absolute path. / 作業を保存して両クライアントを閉じます。ZIPを新しいフォルダーにすべて展開し、`Install.bat` を実行します。初回はプロジェクトの絶対パスを入力します。
2. Reopen the clients. Confirm `local_handoff` under the client MCP list and ask the client to run `handoff_status` on your project. / 両方を開き直し、MCP一覧の `local_handoff` と、対象フォルダーでの `handoff_status` を確認します。
3. For a new version, download and extract its ZIP separately and run the same batch. The installed launcher switches versions and reuses the database, registered roots and client registrations. / 新版は別フォルダーへ展開し、同じバッチを実行します。起動先の版を切り替え、データベース・作業場所・両クライアントの登録を引き継ぎます。

Client registration is stored in `%USERPROFILE%\.codex\config.toml` and `%USERPROFILE%\.gemini\config\mcp_config.json`. If either client already has a different `local_handoff` entry, installation stops so you can review the existing setup. Existing custom registrations and hooks can be managed in each client. / 両クライアントへの登録先は上記の設定ファイルです。異なる `local_handoff` 登録が見つかったら、既存構成を確認できるようにインストールを止めます。独自設定やフックは各クライアントで管理します。

### Ask an AI agent / AIエージェントに依頼する

If you need help with these steps, send the request below to an agent that can use this PC. / 手順が分からなければ、このPCを操作できるAIエージェントに下の依頼文を送ってください。

```text agent-en
Help me install or update Local Handoff MCP on this Windows PC. Inspect the installed version and the official distribution ZIP I provide. Confirm the intended workspace, then use the matching Install.bat and preserve the existing handoff database and client registrations.
Check for local_handoff in the intended clients and verify it from an authorized workspace with handoff_status. Report any configuration conflict and ask before replacing a registration.
```

```text agent-ja
このWindows PCで Local Handoff MCP の導入または更新を手伝ってください。導入済みの版と、私が指定する公式配布ZIPを確認してください。対象の作業フォルダーを確かめ、対応する Install.bat を実行し、既存の引き継ぎデータベースとクライアント登録を引き継いでください。
各クライアントのMCP設定で local_handoff を確認し、許可済みの作業フォルダーで handoff_status を呼び出してください。既存登録と競合したら、置き換える前に差分を示してください。
```

## Add a project / プロジェクトの追加

The Projects list shows workspaces with saved checkpoints. Installed apps appear separately under AI connections. / 「プロジェクト」には、チェックポイントを保存した作業フォルダーが表示されます。導入済みアプリは「接続先のAI」から確認できます。

1. For a folder already covered by a registered location, open it in your AI client and go to step 3. / 登録済みの範囲にあるフォルダーなら、そのフォルダーをAIで開いて手順3へ進みます。
2. For a new location, use the current version's extracted installer. Run the following command from that folder in a Windows terminal, substituting your project's absolute path, then reopen the dashboard and the AI client to pick up the added location. / 新しい場所なら、現在の版の配布ZIPを展開したフォルダーから次のコマンドを実行します。例のパスを実際の作業フォルダーの絶対パスに置き換え、管理画面とAIを開き直します。
3. Ask the AI client to check `handoff_status` and save the first `handoff_checkpoint` for that workspace with its goal and next step. Select Refresh in the dashboard to see the new project. / AIにそのフォルダーの `handoff_status` を確認し、目的と次の操作を `handoff_checkpoint` で保存するよう依頼します。管理画面の「更新」で一覧に表示されます。

```bat
Install.bat --workspace "C:\Projects\Example"
```

### Ask an AI agent / AIエージェントに依頼する

If you need help with these steps, send the request below to an agent that can use this PC. / 手順が分からなければ、このPCを操作できるAIエージェントに下の依頼文を送ってください。

```text agent-en
Register this workspace with Local Handoff MCP and make it appear in the dashboard. Read the active project's absolute path, or ask me for it if there is no active project. Run handoff_status for that path first.
If the location is outside the registered roots, add only that workspace with the current version's Install.bat --workspace. Reopen the dashboard and the client as needed, then save the initial handoff_checkpoint with the project's actual goal and next step. Keep any existing handoff record. Confirm the project appears in the dashboard after Refresh.
```

```text agent-ja
この作業フォルダーを Local Handoff MCP の管理画面に表示してください。開いている作業フォルダーの絶対パスを確認してください。開いていない場合は私に対象を聞いてください。まずそのパスで handoff_status を確認してください。
登録範囲外なら現行版の Install.bat --workspace で対象フォルダーだけを追加し、必要に応じて管理画面とAIを開き直してください。既存の引き継ぎ記録を確認し、初回なら実際の目的と次の作業を handoff_checkpoint で保存してください。最後に管理画面の「更新」を押し、一覧に出ることを確認してください。
```

## Handoff / 作業を交代する

- **Start** — Open the same folder and check `handoff_status`, then use `handoff_checkpoint` before editing. / **開始** — 同じフォルダーを開き、状態を確認してからチェックポイントを記録します。
- **Switch** — The first client checkpoints and calls `offer`. The second checks files, jobs and current permission before `resume`. / **交代** — 渡す側は現状を保存して `offer`、受ける側は現物と実行中の処理・許可を確認して `resume` します。
- **Recover** — If work stopped unexpectedly, verify the previous client and jobs have stopped, then record the evidence with `recover` using current authorization. / **復帰** — 途中で止まったときは前任とジョブの状態を確認し、現在の許可と確認根拠をもって `recover` します。
- **Close** — Call `complete` once the requested work is finished. / **完了** — 依頼範囲が完了したら `complete` を記録します。

When saving a checkpoint, keep the original wording. Use goal_en, next_step_en, completed_en, checks_en and active_jobs_en for English translations of Japanese notes. Use the corresponding _ja fields for Japanese translations of English notes. The dashboard uses the translation for the selected language when available. / チェックポイントは原文を残して保存します。原文が日本語なら goal_en、next_step_en、completed_en、checks_en、active_jobs_en に英訳を入れます。英語の原文は対応する _ja 欄に和訳を入れます。管理画面は、選んだ言語の訳文があれば表示します。

The installer adds standing instructions. They help each assistant remember to record work. Editing outside those instructions remains possible, so check the actual workspace and running jobs at the switch. / インストーラーは共通指示を追加し、各アシスタントが作業記録を忘れにくくします。ファイルの実際の編集とジョブの状態は交代時に確認してください。

## Dashboard / 管理画面

After Install.bat, run Dashboard.bat. Run the same batch again to reopen the dashboard after closing the browser tab. It reuses the running local server, or starts it again when needed. Close the first dashboard terminal to stop the server. Use Refresh to scan for clients again. Open a project by its name to see its written notes and recorded observations. / Install.bat の実行後、Dashboard.bat を開きます。ブラウザーのタブを閉じても、同じバッチから管理画面を開き直せます。起動中なら同じサーバーを使い、停止中なら新しく起動します。最初に起動した端末を閉じるとサーバーが止まります。「更新」でAIを再検出し、案件名を選ぶと引き継ぎの詳細と観測履歴を表示します。

Use English or 日本語 in the header to switch the dashboard and guide language. The dashboard checks AI connections and local runtime ports every minute while the tab is visible. Use Refresh for an immediate scan and the latest project records. Displayed times use your browser's time zone. / ヘッダーの「English」「日本語」で管理画面とマニュアルの言語を切り替えられます。管理画面を表示している間は接続先のAIとローカルAIのポートを1分ごとに確認します。すぐに再検出する場合や案件一覧を読み直す場合は「更新」を選びます。時刻はブラウザーのタイムゾーンで表示します。

Detection covers standard Windows installations and commands on PATH for Codex, Antigravity, Claude Code, OpenCode and Strata. The dashboard also checks the standard local endpoints for Ollama (11434) and LM Studio (1234). Registration indicates the client has an enabled local_handoff entry. Confirm a live connection in that client's MCP list. When sign-in status is unavailable, the dashboard says so. / Codex、Antigravity、Claude Code、OpenCodeの標準的な導入先と、PATH上の対応コマンドを検出します。StrataはWSL内の対応環境を検出します。Ollama（11434）とLM Studio（1234）は標準ポートの応答を確認します。WindowsのLM Studioが起動している場合は、公式CLIで標準以外の設定・待受ポートも確認します。MCP登録表示は、有効な local_handoff 設定があることを示します。実際の接続はクライアントのMCP一覧で確認してください。認証状況を取得できない製品や版では未確認と表示します。

## Codex setup / Codexの設定

Check the Codex row in the Local Handoff MCP dashboard for a registration. If a registration is present, check for `local_handoff` in Codex's MCP settings. If you are setting it up for the first time, open the full manual and follow Install or update. / 管理画面のCodex欄でMCP登録の表示を確認します。登録済みなら、CodexのMCP設定で `local_handoff` を確認します。初回のセットアップは「マニュアル全体」の「導入・更新」を参照してください。

### Ask an AI agent / AIエージェントに依頼する

If you need help with these steps, send the request below to an agent that can use this PC. / 手順が分からなければ、このPCを操作できるAIエージェントに下の依頼文を送ってください。

```text agent-en
Set up Local Handoff MCP for the Codex installation I use on this PC. Check its existing local_handoff registration and the installed Local Handoff MCP launcher. Use the app's supported Codex setup for any missing registration, keeping other Codex settings.
Verify that Codex lists local_handoff and can call handoff_status for the workspace I am using. Tell me if a reload or sign-in needs my action.
```

```text agent-ja
このPCで使っているCodexに Local Handoff MCP をつないでください。既存の local_handoff 登録と導入済みのランチャーを照合し、未登録なら正式なCodex向け手順で追加してください。
CodexのMCP一覧と、私が使っている作業フォルダーでの handoff_status 呼び出しを確認してください。開き直しやログインに私の操作が必要なら、その画面と操作を案内してください。
```

## Antigravity setup / Antigravityの設定

Check the Antigravity row in the dashboard. If MCP is registered, check that `local_handoff` appears and is enabled in Antigravity's MCP settings. For a first-time setup, open the full manual and follow Install or update. If sign-in is needed, choose Open Antigravity and sign in inside the app. / 管理画面のAntigravity欄でMCP登録の表示を確認します。登録済みなら、AntigravityのMCP設定で `local_handoff` が表示され、有効になっているか確認します。初回のセットアップは「マニュアル全体」の「導入・更新」を参照してください。ログインが必要なら「Antigravityを開く」を選び、アプリ内で認証します。

### Ask an AI agent / AIエージェントに依頼する

If you need help with these steps, send the request below to an agent that can use this PC. / 手順が分からなければ、このPCを操作できるAIエージェントに下の依頼文を送ってください。

```text agent-en
Connect Local Handoff MCP to the installed Antigravity. Check for an enabled local_handoff entry in its MCP settings and use the app's supported Antigravity setup if it is missing.
Open the normal Antigravity sign-in screen if needed and let me handle the sign-in. Verify the MCP listing and handoff_status from my authorized workspace.
```

```text agent-ja
導入済みのAntigravityに Local Handoff MCP をつないでください。AntigravityのMCP設定で有効な local_handoff があるか確認し、未登録なら正式なAntigravity向け手順で追加してください。
認証が必要なら正規の認証画面を開いてください。ログインは私が操作します。MCP一覧と、許可済みの作業フォルダーでの handoff_status 呼び出しを確認してください。
```

## Claude Code setup / Claude Codeの設定

After installing Claude Code, select Register MCP in the dashboard. It uses Claude Code's user-scope registration command. Reopen Claude Code and use /mcp to confirm the connection. If Claude Code supports the dedicated login command, use Open authentication page. Older versions open Claude Code in a terminal. First-time users select a theme and login method. In an already configured terminal, enter /login. / Claude Codeを導入し、管理画面で「MCPを登録」を選びます。Claude Codeのユーザー設定へ登録されます。Claude Codeを開き直し、/mcp で接続を確認します。専用ログインコマンドに対応した版では「認証ページを開く」を選びます。旧版はClaude Codeの端末を開きます。初回はテーマとログイン方法を選び、設定済みの端末では /login を入力すると、公式ページがブラウザーに開きます。

Before editing, call handoff_status with the absolute workspace. Save a checkpoint at the start, after a milestone and before handing off. Use recipient when offering to Claude Code or OpenCode, and previous_owner when recovering from either. / 編集前に対象を handoff_status で照合します。開始時、工程の区切り、交代前にチェックポイントを残します。Claude CodeやOpenCodeを宛先にするときは recipient を、両者が前任の復帰では previous_owner を指定します。

```json
{"workspace":"C:/Projects/Example","action":"offer","recipient":"claude-code"}
```

### Ask an AI agent / AIエージェントに依頼する

If you need help with these steps, send the request below to an agent that can use this PC. / 手順が分からなければ、このPCを操作できるAIエージェントに下の依頼文を送ってください。

```text agent-en
Register Local Handoff MCP for the installed Claude Code. Check existing MCP settings and use Register MCP in the Local Handoff MCP dashboard if it is available.
If Claude Code needs sign-in, open its normal authentication flow for me to complete. Reopen Claude Code, check /mcp and try handoff_status in my authorized workspace.
```

```text agent-ja
導入済みのClaude Codeに Local Handoff MCP を登録してください。既存のMCP設定を確認し、管理画面に「MCPを登録」が表示されていればその操作を使ってください。
認証が必要なら私が操作できる正規の認証画面を開いてください。Claude Codeを開き直し、/mcp の表示と許可済みの作業フォルダーでの handoff_status 呼び出しを確認してください。
```

## OpenCode and local models / OpenCodeとローカルモデル

If OpenCode is missing and your WSL Ubuntu is x64, choose Install OpenCode CLI in the OpenCode row. The dashboard downloads a pinned official binary, verifies the npm package integrity and installs it under Local Handoff MCP's WSL directory. Use Refresh to see the result. For the desktop app, choose the official installation guide. / OpenCodeが未検出でWSL Ubuntuがx64の場合は、OpenCode欄の「OpenCode CLIをインストール」を選びます。公式の固定版を取得し、npm配布物の整合性を確認してからLocal Handoff MCPのWSL専用フォルダーに入れます。「更新」で結果を確認できます。デスクトップアプリは「公式インストール手順」から入手します。

Open the managed CLI from Ubuntu with `~/.local/share/local-handoff-mcp/bin/opencode`. Follow the setup in OpenCode if you need to connect an account or model. / 専用CLIはUbuntuで `~/.local/share/local-handoff-mcp/bin/opencode` を実行して起動します。アカウントやモデルの接続が必要ならOpenCode側で設定します。

Use the installed OpenCode version's local MCP configuration. For a Windows OpenCode client, set its local server command array to the following example. Replace YOUR_WSL_USER with your Ubuntu username. For OpenCode running inside Ubuntu, use the same arguments from /usr/bin/python3 onward. / OpenCodeの版に合うローカルMCP設定を使います。Windows版では次のコマンド配列を指定し、YOUR_WSL_USER をUbuntuのユーザー名に置き換えます。Ubuntu内のOpenCodeでは /usr/bin/python3 以降を同じ順で指定します。

```json
["wsl.exe","-d","Ubuntu","--exec","/usr/bin/python3","-B","/home/YOUR_WSL_USER/.local/share/local-handoff-mcp/launch.py","--host","opencode","serve"]
```

Use the name local_handoff and type local. OpenCode v1 places the entry under mcp; v2 places it under mcp.servers. Confirm it with opencode mcp list. Select a local model that supports tool calls. Plain chat or inference software needs a client that can call MCP tools. / 名前は local_handoff、type は local を指定します。OpenCode v1 は mcp 配下、v2 は mcp.servers 配下に登録します。opencode mcp list で接続を確認し、ツール呼び出しに対応したローカルモデルを選択します。

[OpenCode MCP](https://opencode.ai/docs/mcp-servers/) · [Ollama setup for OpenCode](https://docs.ollama.com/integrations/opencode) · [LM Studio local API](https://lmstudio.ai/docs/developer/core/server)

### Ask an AI agent / AIエージェントに依頼する

If you need help with these steps, send the request below to an agent that can use this PC. / 手順が分からなければ、このPCを操作できるAIエージェントに下の依頼文を送ってください。

```text agent-en
Set up Local Handoff MCP in the OpenCode installation I use. Determine whether it runs in Windows or WSL and check its installed version, active config and existing MCP entries. Add only a missing local_handoff entry with the correct local command and host opencode.
Check the result with opencode mcp list and, if an already configured model can call tools, verify handoff_status in my authorized workspace.
```

```text agent-ja
このPCで使っているOpenCodeに Local Handoff MCP をつないでください。Windows版かWSL版か、利用中の版と設定ファイル、既存のMCP登録を確認してください。未登録なら、その版で使えるローカルコマンドとホスト opencode を指定して local_handoff を追加してください。
opencode mcp list で接続状況を確認してください。設定済みのモデルでツールが使える場合は、許可済みの作業フォルダーで handoff_status を呼び出してください。
```

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

### Ask an AI agent / AIエージェントに依頼する

If you need help with these steps, send the request below to an agent that can use this PC. / 手順が分からなければ、このPCを操作できるAIエージェントに下の依頼文を送ってください。

```text agent-en
Connect Local Handoff MCP to the Strata installation in WSL. Inspect Settings → Tools for an existing registration. Add a missing Local Handoff tool server using the installed launcher, the WSL Python path and host strata.
Use Strata's tool test or MCP listing to confirm discovery. If an already configured model is available, check handoff_status in my authorized workspace.
```

```text agent-ja
WSL版Strataに Local Handoff MCP をつないでください。Settings → Tools で既存の登録を確認し、未登録なら導入済みのランチャーとWSLのPythonのパスを使い、ホスト strata で「Local Handoff」を追加してください。
StrataのツールテストやMCP一覧で登録を確認してください。設定済みのモデルが使える場合は、許可済みの作業フォルダーで handoff_status を呼び出してください。
```

## Connect unregistered MCP apps / 未登録のMCP対応アプリをまとめて追加

Copy the request and send it to an AI agent that can access this PC. / 「依頼文をコピー」を押して、このPCを操作できるAIエージェントに貼り付けてください。

```text agent-en
Inspect the installed Windows and WSL apps and CLI tools on this PC. Find MCP clients that support local stdio and have a distinct host identity supported by the installed version of Local Handoff MCP. Start with the dashboard and check the installed apps and their documentation for compatible clients missing from its list.
For each compatible app, check the active profile and its existing MCP settings. Register Local Handoff MCP only where it is missing. Use the installed launcher and the app's supported registration method. Keep existing entries, settings and authorized workspace roots. If another registration uses the same name or an app needs new permissions, software or sign-in, tell me what is required before making that change.
Verify the registration in the client's own MCP listing or connection test. Where the app can call an MCP tool, run the read-only handoff_status on an already authorized workspace. Report which apps were newly registered and verified, already configured, or still require action. Identify apps that need an unsupported host identity without reusing another app's identity.
```

```text agent-ja
このPCにインストール済みのWindows・WSLのアプリとCLIを調べてください。ローカルSTDIOのMCPクライアントで、導入済みの Local Handoff MCP がそのアプリ専用のホスト名に対応しているものが対象です。管理画面の一覧を手がかりに、表示されていない候補も実際の導入状況と製品の手順で確認してください。
対応アプリごとに利用中のプロファイルと既存のMCP設定を確認し、Local Handoff MCP が未登録のものをまとめて追加してください。導入済みのランチャーとアプリの正規の登録方法を使い、既存の登録・設定・作業フォルダーの許可範囲を保持してください。同名の既存登録と競合する場合や、権限の追加、ソフトの導入、ログインが必要な場合は、操作前に何が必要か教えてください。
登録後は各アプリのMCP一覧か接続テストで確認してください。ツールを呼び出せる場合は、許可済みの作業フォルダーで読み取り用の handoff_status を試してください。新たに登録・確認できたもの、登録済みだったもの、操作が残るものを報告してください。専用ホスト名が非対応のアプリは別アプリの名前を流用せず、その旨を知らせてください。
```

## Scheduled observations / 定期観測

Run Autosave.bat after installation. To run it periodically, configure Windows Task Scheduler for your own account and point it at the extracted Autosave.bat. One run saves the first observation, then saves only changes to observable workspace metadata. Only active projects are sampled. / 導入後に Autosave.bat を実行できます。定期実行する場合はWindowsタスク スケジューラで自分のアカウントを使い、展開した Autosave.bat を指定します。初回と観測情報に変化があるときに保存します。対象は担当ありの案件です。

History retains up to 100 written checkpoints and 100 automated observations per workspace. Automated observations do not back up file contents, infer work progress or confirm job status. Keep recording intent, verification and job observations with handoff_checkpoint. / 作業フォルダーごとにチェックポイントと自動観測を各100件まで保持します。自動観測の対象はGitメタデータ等です。ファイル本体のバックアップ、進捗の推測、ジョブの稼働確認は別途行い、目的・検証結果・ジョブの確認結果は handoff_checkpoint に記録します。

### Ask an AI agent / AIエージェントに依頼する

If you need help with these steps, send the request below to an agent that can use this PC. / 手順が分からなければ、このPCを操作できるAIエージェントに下の依頼文を送ってください。

```text agent-en
Help me configure scheduled observations for Local Handoff MCP. Find the installed version's Autosave.bat and check whether my Windows user already has a task for it. Ask me for the interval if I have not specified it.
Use Windows Task Scheduler for my user at the agreed interval. Run the task once and verify its result and the observation history for a permitted active workspace.
```

```text agent-ja
Local Handoff MCP の定期観測を設定してください。このPCの版に対応する Autosave.bat と、同じ処理のタスクが登録済みかを確認してください。実行間隔を私が指定していなければ聞いてください。
合意した間隔で私のWindowsアカウントのタスクとして設定してください。一度実行し、実行結果と、観測対象の作業フォルダーの履歴を確認してください。
```

## Local data / ローカルデータ

The data directory is `~/.local/share/local-handoff-mcp` inside Ubuntu. To back up or manually migrate an installation, close both clients first and preserve `settings.json` and the SQLite database together. It can contain project paths and work notes. Treat both as private. / データの保管場所はUbuntu内の上記フォルダーです。バックアップや移行は両クライアントを閉じたうえで、`settings.json` とSQLiteデータベースを一緒に保管します。作業場所や進捗が含まれるため、非公開で保管してください。
