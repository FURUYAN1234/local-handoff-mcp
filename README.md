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
