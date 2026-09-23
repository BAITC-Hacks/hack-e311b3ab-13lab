"""Meeting platform integrations.

Connectors turn a platform meeting (or a browser tab) into the normalized events in
`events.py`. They contain no AI logic: the live session in `app.live` consumes any
connector the same way and feeds the existing pipeline.
"""
