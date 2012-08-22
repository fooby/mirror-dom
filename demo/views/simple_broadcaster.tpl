<!DOCTYPE html>
<html>
    <head>
        <!-- mirrordom dependency if you are using the default JQueryXHRPusher -->
        <script type="text/javascript"
            src="/static/json2.js"></script>
        <script type="text/javascript"
            src="/static/mirrordom/broadcaster.js"></script>
        <!-- not a mirrordom dependency, just makes doing the demo page 
            easier -->
        <script type="text/javascript"
            src="https://ajax.googleapis.com/ajax/libs/jquery/1.7.2/jquery.min.js"></script>
        <script type="text/javascript">
            jQuery(function() {
                var broadcaster = new MirrorDom.Broadcaster({
                    root_url: "{{mirrordom_uri}}/"
                });
                broadcaster.start();
                $("#spawn").click(function() {
                    $("body").append("<p>Something</p>");
                    return false;
                });
            });
        </script>
    </head>
    <body>
        <h1>Broadcasting test</h1>
        <img src="/static/smiley.png"/>
        <form>
            <button id="spawn">Spawn Something</button>
        </form>
    </body>
</html>
