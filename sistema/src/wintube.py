#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LibertyTube — abrir o app.

    python wintube.py

Este arquivo só chama o pacote `wintube`. Toda a lógica está em
src/wintube/ (core, backend, pipeline, ui).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wintube.main import executar  # noqa: E402

if __name__ == "__main__":
    sys.exit(executar())
