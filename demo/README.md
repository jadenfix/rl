# Reward edit-similarity demo

This GIF and MP4 are rendered from responses captured from the real local reward
HTTP process. The renderer first checks the runtime files against
`source-manifest.json`, runs the reward regression suite, then exercises health,
unchanged text, rewritten text, malformed JSON, an oversized request, and
Prometheus metrics.

```bash
python -m pip install -r demo/requirements.txt
python demo/render_demo.py
```

`receipt.json` records the actual responses and fixture-only scope.
`artifacts.json` records each published artifact's byte size and SHA-256 digest.
CI runs `python demo/verify_artifacts.py` to reject truncated or replaced media.
The score is only a deterministic text-change signal; the demo makes no claim
about model quality, user satisfaction, or business impact.
