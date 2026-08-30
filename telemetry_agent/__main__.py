"""Production entry point; intentionally accepts no remote-control parameters."""

from .agent import main

raise SystemExit(main())
