var MirrorDom = MirrorDom === undefined ? {} : MirrorDom;

//MirrorDom.Base.prototype.get_document_element = function() {
//    var d = this.get_document_object();
//    var doc_elem = d.documentElement;
//    return doc_elem;
//}

MirrorDom.Util = {}

/**
 * @param iframe        Iframe object
 */
MirrorDom.Util.get_document_object_from_iframe = function(iframe) {
    var d = null;
    if (iframe) {
        // Retrieve iframe document
        if (iframe.contentDocument) {
            // Firefox
            d = iframe.contentDocument;
        }
        else if (iframe.contentWindow) {
            // IE
            d = iframe.contentWindow.document;
        }
        else {
            console.log("What the hell happened");
        }
    }
    else {
        throw new Error("iframe has not been set");
    }

    return d;
}

/**
 * Checks whether we should ignore the node when building the tree
 */
MirrorDom.Util.should_skip_node = function(node) {
}
