<!DOCTYPE html>
<html>
    <head>
        <script type="text/javascript" src="/static/mirrordom/common.js"></script>
        <script type="text/javascript" src="/static/mirrordom/viewer.js"></script>
        <!-- not a mirrordom dependency, just makes doing the demo page 
            easier -->
        <script type="text/javascript"
            src="http://ajax.googleapis.com/ajax/libs/jquery/1.7.2/jquery.min.js"></script>
        <script type="text/javascript">
            jQuery(function() {
                var viewer = new MirrorDom.Viewer({
                    root_url: "{{mirrordom_uri}}/",
                    iframe: document.getElementById("mirrordom_iframe"),
                    blank_page: "{{blank_page}}",
                    debug: true
                });

                var POLL_INTERVAL = 2000;
                window.setInterval(jQuery.proxy(viewer, "go"), POLL_INTERVAL);
            });
        </script>
    </head>
    <body>
        <h1>mirrordom viewer demo</h1>
        <div id="mirrordom-container">
            <iframe id="mirrordom_iframe" style="overflow: hidden; width:100%; height:30cm;">
        </div>
    </body>
</html>
