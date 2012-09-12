/**
 * MirrorDom viewer proof of concept
 */

var MirrorDom = MirrorDom === undefined ? {} : MirrorDom;

MirrorDom.Viewer = function(options) {
    this.receiving = false;
    this.interval_event = null;
    this.iframe = null;

    // Keep a reference to all frames. Possible keys are:
    //
    //      m: Main viewer frame
    //      <comma separated node path>,i: Iframe
    this.frames = {}
    
    // Misc
    this.debug = false;

    this.next_change_id = null;
    this.init_options(options);
}

MirrorDom.Viewer.prototype.init_options = function(options) {
    if (options.puller) {
        this.puller = options.puller;
    } else {
        this.puller = new MirrorDom.JQueryXHRPuller(options.root_url);
    }

    this.iframe = options.iframe;
    this.poll_interval = options.poll_interval != null ? options.poll_interval : 1000;
    this.debug = options.debug;
};

// ----------------------------------------------------------------------------
// Public functions
// ----------------------------------------------------------------------------

MirrorDom.Viewer.prototype.start = function(container_id) {
    var self = this;
    self.poll();
    this.interval_event = window.setInterval(function() {
        self.poll();
    }, this.poll_interval);
};

// ----------------------------------------------------------------------------
// Internal logic
// ----------------------------------------------------------------------------
MirrorDom.Viewer.prototype.poll = function() {
    var d = this.get_document_object();
    if (d.readyState != "complete") {
        this.log("Page is loading, skip poll");
        return;
    }
    
    if (this.receiving) {
        this.log("Already receiving, aborting");
        return;
    }

    this.log("Polling");

    this.receiving = true;
    var self = this;
    var params = {};
    if (this.next_change_id != null) {
        params["change_id"] = this.next_change_id;
    }
    this.puller.pull("get_update", params, 
        function(result) {
            self.receive_updates(result);
            self.receiving = false;
        }
    );
}

MirrorDom.Viewer.prototype.receive_updates = function(result) {

    var changelogs = result["changesets"];

    var doc_elem = this.get_document_element();

    // We have a list of changelogs for each iframe in our document.
    // The changelogs are ordered top to bottom, since the higher up frames
    // need to create the lower frames first, before those frame documents can
    // be managed.


    // Special handling for iframes, which may need to be specially managed
    var self = this;
    var make_apply_iframe_func = function(iframe, cs, frame_path) {
        return function() {
            console.log("Going for " + frame_path.join(",") + "!");
            self.log("Applying changeset to " + frame_path.join(","));
            var d = MirrorDom.Util.get_document_object_from_iframe(iframe);
            self.apply_changeset(d.documentElement, cs);
        }
    }
    
    for (var i = 0; i < changelogs.length; i++) {
        var frame_path = changelogs[i][0];
        var changeset = changelogs[i][1];

        // Don't bother with this changeset
        if (!("diffs" in changeset)) {
            continue;
        }

        // Locate the iframe
        var apply_node = MirrorDom.Util.node_at_upath(doc_elem, frame_path);

        if (frame_path[frame_path.length-1] == 'i') {
            // Handle iframe
            var iframe = apply_node;

            apply_func = make_apply_iframe_func(iframe, changeset, frame_path);

            d = MirrorDom.Util.get_document_object_from_iframe(iframe);
            if (d.readyState != 'complete') {
                jQuery(iframe).one("load.mirrordom", apply_func);
            } else {
                apply_func();
            }
        } else if (frame_path[frame_path.length-1] == 'm') {
            // Main iframe
            this.apply_changeset(doc_elem, changeset);
        }

    }

    this.next_change_id = result["last_change_id"] + 1;
}

MirrorDom.Viewer.prototype.apply_changeset = function(doc_elem, changelog) {
    if (changelog.init_html) {
        this.log(changelog.last_change_id + ": Got new html!");
        this.apply_document(doc_elem, changelog.init_html);
    }

    if (changelog.diffs) {
        this.log(changelog.last_change_id + ": Applying diffs");
        this.apply_diffs(doc_elem, changelog.diffs);
    }
}

// ----------------------------------------------------------------------------
// Internal utility functions
// ----------------------------------------------------------------------------

MirrorDom.Viewer.prototype.get_document_object = function() {
    return MirrorDom.Util.get_document_object_from_iframe(this.iframe);
}

MirrorDom.Viewer.prototype.get_document_element = function() {
    return this.get_document_object().documentElement;
}

// ----------------------------------------------------------------------------
// DOM functions
// ----------------------------------------------------------------------------
MirrorDom.Viewer.prototype.apply_attrs = function(changed, removed, node, ipath) {
    for (var name in changed) {
        var value = changed[name];
        node.setAttribute(name, value);
    }

    for (var i = 0; i < removed.length; i++) {
        node.removeAttribute(removed[i]);
    }
}

MirrorDom.Viewer.prototype.apply_props = function(changed, removed, node, ipath) {
    for (var name in changed) {
        var value = changed[name];
        var path = name.split('.');
        MirrorDom.Util.set_property(node, path, value, false);
    }

    for (var name in removed) {
        // Hmm...I don't think this is valid actually, TODO: remove removed
    }
};

MirrorDom.Viewer.prototype.apply_head_html = function(doc_elem, head_html) {
    var head = doc_elem.getElementsByTagName('head')[0];
    var new_doc = jQuery.parseXML('<head>' + head_html + '</head>');
    var head = jQuery(head);
    new_doc.children().each(function() {
        jQuery(this).appendTo(head);
    });
}

/**
 * Takes in a browser native XML element (NOT jquery wrapped)
 */
MirrorDom.Viewer.prototype.xml_to_string = function(xml_node) {
    var s;
    //IE
    if (typeof window.XMLSerializer != "undefined"){
        s = (new XMLSerializer()).serializeToString(xml_node);
    } else if (typeof xml_node.xml != "undefined") {
        s = xml_node.xml;
    } else{
        throw new Error("Can't serialise XML node?");
    }
    return s;
}

/**
 * @param use_innerhtml     False if appending child by child
 *                          True if building an XML fragment to dump into the
 *                          node as one big lump
 *                          
 */
MirrorDom.Viewer.prototype.copy_to_node = function(xml_node, dest, use_innerhtml) {
    var children = xml_node.children();
    if (use_innerhtml) {
        var inner_html = [""];
        for (var i = 0; i < children.length; i++) {
            var new_node = children[i];
            var new_xml  = this.xml_to_string(new_node);
            inner_html.push(new_xml);
        }
        dest.html(inner_html.join(""));
    }
    else {
        for (var i = 0; i < children.length; i++) {
            var new_node = children[i];
            // TODO...can we just chuck the node straight in without converting
            // back to a string?
            dest.append(this.xml_to_string(new_node));
        }
    }
}

/**
 * Gets the output of Broadcaster.get_document and reproduces it against
 * the current document element.
 *
 * EXPECTS WELL FORMED XML. If you rip innerHTML (which is HTML but
 * not well formed XML) out of a document and chuck it back in here, that won't
 * work.
 *
 * @param doc_elem      null for root document element, but this will be called
 *                      with child iframe document elements too.
 */
MirrorDom.Viewer.prototype.apply_document = function(doc_elem, data) {
    //doc_elem = doc_elem == null ? this.get_document_element() : doc_elem;

    //var full_html = ['<html>', html, '</html>'].join("");
    // note that viewer won't execute scripts from the client
    // because we use innerHTML to insert (although the
    // <script> elements will still be in the DOM)
    //doc_elem.innerHTML = full_html;
    //console.log(full_html);
    //jQuery(doc_elem).html(full_html);
    //console.log(full_html);
    
    var new_doc = jQuery(jQuery.parseXML(data));
    var new_head_node = new_doc.find("head");

    if (new_head_node.length > 0) {
        var current_head = doc_elem.getElementsByTagName('head')[0];
        current_head = jQuery(current_head).empty();
        this.copy_to_node(new_head_node, current_head, false);
    }

    var current_body = doc_elem.getElementsByTagName('body')[0];

    if (current_body == null) {
        console.log(doc_elem.innerHTML);
        throw new Error("No current body, what's going on?!");
    }

    current_body = jQuery(current_body).empty();
    current_body[0].style.cssText = "";

    var new_body_node = new_doc.find("body");
    this.copy_to_node(new_body_node, current_body, true);

    /*var body = doc_elem.getElementsByTagName('body')[0];

    var head_html = data[0];
    var body_html = data[1];
    body.innerHTML = body_html;

    this.apply_head_html(doc_elem, head_html);*/
}

/**
 * Apply diffs to a tree.
 *
 * @param node      DOM node to start applying from. If null
 *                  then use document element.
 *
 * @param index     Index in changeset diffs (for debugging log messages only)                 
 */
MirrorDom.Viewer.prototype.apply_diffs = function(node, diffs, index) {
    if (node == null) { node = this.get_document_element(); }
    var root = node;

    for (var i=0; i < diffs.length; i++) {
        var diff = diffs[i];        
        // Diff structure:
        //
        // 0) "node", "text", "deleted", "attribs", "props"
        // 1) Path to node (node offsets at each level of tree)
        //
        // For "node", "text":
        // 2) Inner HTML
        // 3) Element definition:
        //    - attributes: HTML attributes
        //    - nodeName:   Node name
        //    - nodeType:   Node type
        // 4) Extra properties to apply
        //
        // For "attribs", "props":
        // 2) Dictionary of changed attributes
        // 3) Dictionary of removed attributes (may be omitted)
        //
        // For "deleted":
        // nope

        if (diff[0] == 'node' || diff[0] == 'text') {
            var parent = MirrorDom.Util.node_at_path(root, 
                diff[1].slice(0, diff[1].length-1));

            var node = parent.firstChild;
            node = MirrorDom.Util.apply_ignore_nodes(node);

            // Go to node referenced in offset and replace it 
            // if it exists; and delete all following nodes
            for (var d=0; d < diff[1][diff[1].length-1]; d++) {
                node = node.nextSibling;
                node = MirrorDom.Util.apply_ignore_nodes(node);
            }

            // Wipe everything out, as we're assuming the diff contains a
            // reconstruction of ALL our remaining sibling nodes.
            this.delete_node_and_remaining_siblings(node);

            // Create new element from the cloned node
            if (diff[0] == 'node') {
                var cloned_node = diff[3];
                var new_elem = document.createElement(cloned_node.nodeName);
                for (var k in cloned_node.attributes) {
                    new_elem.setAttribute(k, cloned_node.attributes[k]);
                }
                jQuery(new_elem).html(diff[2]);

                // Apply all properties which doesn't get transmitted in
                // innerHTML. Properties are in the form [path, property_dictionary]
                // where path is relative to the newly added node.
                var props = diff[4];
                for (var j=0; j < props.length; j++) {
                    var ppath = props[j][0];
                    var pnode = MirrorDom.Util.node_at_path(new_elem, ppath);
                    this.apply_props(props[j][1], null, pnode, ppath);
                }
                this.apply_diffs(new_elem, diff[4]);
            } else {
                var new_elem = document.createTextNode(diff[2]);
            }
            parent.appendChild(new_elem);

        } else if (diff[0] == 'attribs') {
            // diff[2] = changed attributes
            // diff[3] = removed attributes
            var node = MirrorDom.Util.node_at_path(root, diff[1]);
            this.apply_attrs(diff[2], diff[3], node, diff[1]);
        } else if (diff[0] == 'props') {
            // diff[2] = changed properties
            // diff[3] = removed properties (may not exist)
            var removed = (diff.length == 4) ? diff[3] : null;
            var node = MirrorDom.Util.node_at_path(root, diff[1]);
            this.apply_props(diff[2], removed, node, diff[1]);
        } else if (diff[0] == 'deleted') {
            var node = MirrorDom.Util.node_at_path(root, diff[1]);
            this.delete_node_and_remaining_siblings(node);
        } 
    }
}

// ----------------------------------------------------------------------------
// Utility functions
// ----------------------------------------------------------------------------

/**
 * Deletes a node and all its siblings to the right
 */
MirrorDom.Viewer.prototype.delete_node_and_remaining_siblings = function(node) {
    if (node == null) {
        return;
    }

    var parent = node.parentNode;
    while (node) {
        var next_node = node.nextSibling;
        parent.removeChild(node);
        node = next_node;
    }
}

// ----------------------------------------------------------------------------
// Debug functions
// ----------------------------------------------------------------------------
MirrorDom.Viewer.prototype.log = function(msg) {
    if (this.debug && window.console && console.log) {
        console.log(msg);
    }
}


// ----------------------------------------------------------------------------
// Helper classes
// ----------------------------------------------------------------------------
MirrorDom.JQueryXHRPuller = function(root_url) {
    this.root_url = root_url;
};

MirrorDom.JQueryXHRPuller.prototype.pull = function(method, args, callback) {
    if (method == "get_update") {
        args.change_ids = JSON.stringify(args.change_ids);
    }
    jQuery.get(this.root_url + method, args, callback);
};
