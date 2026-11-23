# Release maintenance / リリース時の文書更新

1. Inspect the actual release diff and tests. Update the version and the affected scope, implementation, data and verification sections in both technical papers. / リリース差分と検証結果を確認し、日英両論文の版と、対象・実装・データ・検証で影響を受ける箇所を更新します。
2. Run `/usr/bin/python3 -B check_release_docs.py` before building distribution files. The check requires both papers to identify the release version. A passing check confirms version alignment. Review the content against the implementation separately. / 配布物を作る前に文書検査を実行します。日英論文の版が揃っていることを確認できます。本文の事実は実装と照合します。
3. After approval, publish the matching tagged ZIP and update the two published paper documents at their existing URLs. Read back the documents and note's links. / 正式公開の承認後、タグと同じZIPを配布し、公開済み日英論文は既存URLのまま更新します。論文とnoteの案内を読み戻します。
4. Compare the change with the AI Manga Creative Suite note and the Japanese and English suite papers. Update affected statements in both papers when the published inventory, integration, inputs, supported environments or data handling changes. Preserve unrelated sections and verify through the existing public links. / 総合noteとSuiteの日英論文も公開実態と照合します。構成、連携、入出力、動作環境、データの扱いに変化があれば両論文の該当箇所を更新し、既存公開リンクで確認します。
