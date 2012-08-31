var MDTestUtil = {

    // Get iframe document
    get_iframe_document: function(iframe) {
        // Retrieve iframe document
        if (iframe.contentDocument) {
            // Firefox
            d = iframe.contentDocument;
        }
        else if (iframe.contentWindow) {
            // IE
            d = iframe.contentWindow.contentDocument;
        }
        else {
            console.log("What the hell happened");
        }

        return d;
    },

    get_html: function(iframe) {
        var d = MDTestUtil.get_iframe_document(iframe);
        var de = d.documentElement;
        var html = jQuery(de).clone().wrap('<p>').parent().html();
        return html;
    }

}

MDTestUtil.TestTransport = function() {
    this.messages = [];
};

    
/**
 * Mirrordom Pusher interface
 */
MDTestUtil.TestTransport.prototype.push = function(method, args, callback) {
    //req.callJSON("showme2.mirrordom_msg", [this.session_id, method, args], callback);
};

/**
 * Mirrordom Puller interface
 */
MDTestUtil.TestTransport.prototype.pull = function(method, args, callback) {
    //req.callJSON("showme2.mirrordom_msg", [this.session_id, method, args], callback);
};
