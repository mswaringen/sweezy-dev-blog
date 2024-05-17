Title: My First Review
Date: 2010-12-03 10:20
Category: Review

Following is a review of my favorite mechanical keyboard.


    :::python
    @task
    def serve(c):
        """Serve site at http://$HOST:$PORT/ (default is localhost:8000)"""

        class AddressReuseTCPServer(RootedHTTPServer):
            allow_reuse_address = True

        server = AddressReuseTCPServer(
            CONFIG["deploy_path"],
            (CONFIG["host"], CONFIG["port"]),
            ComplexHTTPRequestHandler,
        )

        if OPEN_BROWSER_ON_SERVE:
            # Open site in default browser
            import webbrowser

            webbrowser.open("http://{host}:{port}".format(**CONFIG))

        sys.stderr.write("Serving at {host}:{port} ...\n".format(**CONFIG))
        server.serve_forever()