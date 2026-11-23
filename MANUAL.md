# User and MCP setup guide / 操作・MCP設定マニュアル

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

## Local data / ローカルデータ

The data directory is `~/.local/share/local-handoff-mcp` inside Ubuntu. To back up or manually migrate an installation, close both clients first and preserve `settings.json` and the SQLite database together. It can contain project paths and work notes. Treat both as private. / データの保管場所はUbuntu内の上記フォルダーです。バックアップや移行は両クライアントを閉じたうえで、`settings.json` とSQLiteデータベースを一緒に保管します。作業場所や進捗が含まれるため、非公開で保管してください。
