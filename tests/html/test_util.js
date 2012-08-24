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

    get_inner_html: function(iframe) {
        var d = MDTestUtil.get_iframe_document(iframe);
        var de = d.documentElement;
        return de.innerHTML;
    }

}
