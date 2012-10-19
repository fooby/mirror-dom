/**
 * MirrorDom viewer proof of concept
 */

var MirrorDom = MirrorDom === undefined ? {} : MirrorDom;

MirrorDom.RECEIVING_OK = 1;
MirrorDom.RECEIVING_BAD = 2;


/**
 * Constructor. See init_options for option processing
 */
MirrorDom.Viewer = function(options) {
    this.receiving = false;

    // We can be in a good state or a bad state. When in a good state,
    // everything is normal and we apply any page changes received.
    //
    // If we get desynchronised (i.e. we start receiving changes for elements
    // that don't exist), we go into a contingency mode where we don't apply
    // any further changes until the broadcaster visits a new page which gives us a
    // chance to start afresh.
    this.error_status = MirrorDom.RECEIVING_OK;
    this.iframe = null;
    this.event_listeners = {};
    
    // Misc
    this.debug = false;
    this.next_change_id = null;

    // Invoke the remote procedure call
    this.init_options(options);
}

MirrorDom.Viewer.prototype.init_options = function(options) {
    // Setup custom RPC transport mechanism (the data passed needs to
    // eventually get to the python server)
    if (options.pull_method) {
        this.pull_method = options.pull_method;
    } else {
        var puller = new MirrorDom.JQueryXHRPuller(options.root_url);
        this.pull_method = jQuery.proxy(puller, "pull");
    }

    this.iframe = options.iframe;
    // about:blank doesn't work properly in some browsers, so you really do
    // have to provide an actual blank page url.
    this.blank_page = options["blank_page"] != null ? options["blank_page"] : "about:blank";
    this.debug = options.debug;
};

// ----------------------------------------------------------------------------
// Public functions
// ----------------------------------------------------------------------------

/**
 * Perform a single iteration of mirrordom logic.
 *
 * This function should be called at regular intervals to get semi-responsive
 * browser synchronisation. 
 */
MirrorDom.Viewer.prototype.go = function() {
    this.poll();
}

// ----------------------------------------------------------------------------
// Internal logic
// ----------------------------------------------------------------------------

/**
 * This is the start of main logic flow. Called at regular intervals.
 *
 * The effect is to invoke the "puller.pull()" method, with data and a
 * callback. The puller needs to move the data to the Python server via some
 * RPC mechanism, grab the response and then pass that to the callback.
 *
 * In this case, the callback is "receive_updates" which is where the real
 * work begins.
 */
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

    this.receiving = true;
    var self = this;
    var params = {};
    if (this.next_change_id != null) {
        params["change_id"] = this.next_change_id;
    }

    // Inform the server we only want an update if it contains a main frame
    // init_html (this basically means we wait until the broadcaster visits a
    // new page)
    if (this.error_status == MirrorDom.RECEIVING_BAD) {
        // Note: this is extremely hacky, given that the "true" value gets run
        // through JSON on the other end.
        // TODO: Don't be hacky
        params["init_html_required"] = "true";
        this.log("Polling with change " + params["change_id"] + ", using error recovery mode");
    }
    else {
        this.log("Polling with change " + params["change_id"]);
    }

    // Invoke the remote procedure call
    this.pull_method("get_update", params, 
        function(result) {
            if (result) {
                self.receive_updates(result);
            }
            self.receiving = false;
        }
    );
}

/**
 * Callback which expects the response from the python mirrordom server.
 *
 * @param result        The response the python server from whatever method was
 *                      invoked from the .poll() method.
 */
MirrorDom.Viewer.prototype.receive_updates = function(result) {
    if (result["changesets"] == undefined) {
        this.log("No changeset returned (this should only happen in error recovery mode)");
        return;
    }

    if (result["changesets"].length > 0) {
        this.apply_all_changesets(result["changesets"]);
        this.next_change_id = result["last_change_id"] + 1;
    }
}


/**
 * Wraps perform_apply_all_changesets in a try/catch.
 */
MirrorDom.Viewer.prototype.apply_all_changesets = function(changesets, resume_pos) {
    try {
        this.perform_apply_all_changesets(changesets, resume_pos);
    } catch (e) {
        // Got a diff path error, dump debug info to the console
        if (e instanceof MirrorDom.Util.PathError || e instanceof MirrorDom.Util.DiffError) {
            if (this.debug) {
                this.log(e.message);
                this.log("Path analysis: " + e.describe_path());
            }
            this.error_status = MirrorDom.RECEIVING_BAD;
            this.fire_event("on_error_status", {"status": this.error_status});
            return;
        }
        else {
            throw(e);
        }
    }
}

/**
 * Apply a bunch of changesets received from the server.
 *
 * @param changesets        List of [frame_path, changesets]
 * @param resume_pos        Index of changeset to begin processing
 */
MirrorDom.Viewer.prototype.perform_apply_all_changesets = function(changesets, resume_pos) {
    // We have a list of changelogs for each iframe in our document.
    // The changelogs are ordered top to bottom, since the higher up frames
    // need to create the lower frames first, before those frame documents can
    // be managed.
    //
    // This function is RE-ENTRANT due to needing to wait for iframe load
    // events and whatnot.

    var self = this;
    function make_reentry_callback(pos) {
        var executed = false;
        return function() {
            if (executed) {
                self.log("Re-entered on changeset " + pos + ", but already executed");
                return;
            }
            self.log("Re-entry on changeset " + pos);
            executed = true;
            self.apply_all_changesets(changesets, pos);
        }
    }

    // If we're resuming, then that means we came here from an event handler callback
    var has_loaded = resume_pos != undefined;
    
    // This loop is weird...sometimes we have to wait for an iframe to load, at
    // which point we terminate the current loop and resume once the event has
    // fired.
    for (var i = resume_pos ? resume_pos : 0; i < changesets.length; i++) {
        var frame_path = changesets[i][0];
        var changes = changesets[i][1];
        if (!("diffs" in changes || "init_html" in changes)) {
            // Don't bother with this changeset, nothing worth doing
            continue;
        }
        // Locate the iframe
        var iframe = MirrorDom.Util.node_at_upath(this.iframe, frame_path);
        var iframe_doc = MirrorDom.Util.get_document_object_from_iframe(iframe);

        // Commence iframe complexity
        this.log("Changeset " + i + ": Iframe " + frame_path.join(",") +  " ready state: " + iframe_doc.readyState);
        if (iframe_doc.readyState == "uninitialized") {
            this.log("Changeset " + i + ": Initialising iframe: " + i + " on frame " + frame_path.join(","));
            // Unset and re-set it to force a reload
            iframe.src = "";
            // Hack: The "load" event doesn't trigger unless we force
            // retrieving the blank page from the server. So far this has been
            // observed in Firefox.
            iframe.src = this.blank_page + "?" + (new Date()).getTime();
            var callback = make_reentry_callback(i);
            jQuery(iframe).load(callback);
            return;
        } else if (iframe_doc.readyState == 'loading') {
            // Scenario 1: Newly created iframe
            this.log("Changeset " + i + ": Waiting for iframe to finish loading: " + i + " on frame " + frame_path.join(","));
            var callback = make_reentry_callback(i);
            jQuery(iframe).load(callback);
            return;
        } else if ("init_html" in changes && !has_loaded) {
            // Scenario 2: IFrame exists, but we have init_html and want to
            // start fresh. Let's load a blank page first.
            this.log("Changeset " + i + ": Init HTML found for changeset " + i + " on frame " + frame_path.join(",") + ", resetting back to blank page");
            // Unset and re-set it to force a reload
            iframe.src = "";
            iframe.src = this.blank_page;
            var callback = make_reentry_callback(i);
            jQuery(iframe).load(callback);
            return;
        } else {
            // Scenario 3: Have diffs, let's proceed
            this.apply_changeset(iframe_doc.documentElement, changes);

            // Reset variable for next loop
            has_loaded = false;
        }
    }

    // We're at the very end now, let's do some finalisation
    var first_frame_path = changesets[0][0];
    var first_changes = changesets[0][1];
    if (MirrorDom.Util.is_main_upath(first_frame_path)) {
        var iframe = MirrorDom.Util.node_at_upath(this.iframe, first_frame_path);
        var iframe_doc = MirrorDom.Util.get_document_object_from_iframe(iframe);

        // The url element is only supplied whenever init_html is supplied
        if ("url" in first_changes) {
            this.fire_event("on_page_load", {"url": first_changes["url"]});
        }
    }
}

/**
 * Apply a single changeset to a frame document
 */
MirrorDom.Viewer.prototype.apply_changeset = function(doc_elem, changelog) {
    if (changelog.init_html) {
        // init_html means a clean slate, so we're no longer concerned about
        // any previous diff errors encountered.
        if (this.error_status == MirrorDom.RECEIVING_BAD) {
            this.error_status = MirrorDom.RECEIVING_OK;
            this.fire_event("on_error_status", {"status": this.error_status});
        }
        this.log(changelog.last_change_id + ": Got new html!");
        this.apply_document(doc_elem, changelog.init_html);
    }

    if (changelog.diffs) {
        this.log(changelog.last_change_id + ": Applying " + changelog.diffs.length + " diffs");
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
 * @param xml_node          jQuery XML node
 * @param dest              jQuery destination
 *
 * @param use_innerhtml     False if appending child by child
 *                          True if building an XML fragment to dump into the
 *                          node as one big lump
 *                          
 */
MirrorDom.Viewer.prototype.copy_to_node = function(xml_node, dest, use_innerhtml) {
    var children = xml_node[0].childNodes;
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
            var dom_node = MirrorDom.Util.copy_xml_node_to_dom(dest[0].ownerDocument, new_node);
            // Comment nodes don't get copied
            if (dom_node != null) {
                dest[0].appendChild(dom_node);
            }

            //var xml_string = this.xml_to_string(new_node);
            // TODO...can we just chuck the node straight in without converting
            // back to a string?
            //dest.append(xml_string);
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
    var doc_object = doc_elem.ownerDocument;
    var new_doc = jQuery(jQuery.parseXML(data));

    // Set the body
    var current_body = doc_elem.getElementsByTagName('body')[0];
    if (current_body == null) {
        console.log(doc_elem.innerHTML);
        throw new Error("Could not find <body> element in viewer document.");
    }

    current_body = jQuery(current_body).empty();
    var new_body_node = new_doc.find("body");
    this.copy_to_node(new_body_node, current_body, true);

    // Set the head
    var new_head_node = new_doc.find("head");
    if (new_head_node.length > 0) {
        var current_head = doc_elem.getElementsByTagName('head')[0];
        current_head = jQuery(current_head).empty();
        var doc_object = current_head[0].ownerDocument;
        this.log("Stylesheets before: " + doc_object.styleSheets.length);
        var links = new_head_node.find("link");
        this.log("Found " + links.length + " link nodes");
        this.copy_to_node(new_head_node, current_head, false);
        this.log("Stylesheets after: " + doc_object.styleSheets.length);

        // TODO: If we find <style> elements with custom CSS, I don't think it
        // works. A hack will need to be found.
    }
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
        // 1) Type: "html" or "svg"
        // 2) Path to node (node offsets at each level of tree)
        //
        // For "node", "text":
        // 3) Inner HTML
        // 4) Element definition:
        //    - attributes: HTML attributes
        //    - nodeName:   Node name
        //    - nodeType:   Node type
        // 5) Extra properties to apply
        //
        // For "attribs", "props":
        // 3) Dictionary of changed attributes
        // 4) Dictionary of removed attributes (may be omitted)
        //
        // For "deleted":
        // nope

        if (diff[0] == 'node' || diff[0] == 'text') {
            var parent = MirrorDom.Util.node_at_path(root, 
                diff[2].slice(0, diff[2].length-1));

            var node = parent.firstChild;
            node = MirrorDom.Util.apply_ignore_nodes(node);

            // Go to node referenced in offset and replace it 
            // if it exists; and delete all following nodes
            for (var d=0; d < diff[2][diff[2].length-1]; d++) {
                if (node == null) {
                    throw new MirrorDom.Util.DiffError(diff, root, diff[2]); // Path is invalid, throw error
                }
                node = MirrorDom.Util.apply_ignore_nodes(node.nextSibling);
            }

            // Wipe everything out, as we're assuming the diff contains a
            // reconstruction of ALL our remaining sibling nodes.
            this.delete_node_and_remaining_siblings(node);

            var node_type = diff[1];

            // Create new element from the cloned node
            if (diff[0] == 'node') {
                switch (node_type) {
                    case "svg":
                        // TODO: Manage the situation when node corresponds to entire XML doc
                        var svg_doc = parent.ownerDocument;
                        var new_elem = MirrorDom.Util.to_svg(svg_doc, diff[3]);
                        parent.appendChild(new_elem);
                        break;
                    case "html":
                        var new_elem = jQuery(diff[3])[0];
                        parent.appendChild(new_elem);

                        // Apply all properties which doesn't get transmitted in
                        // innerHTML. Properties are in the form [path, property_dictionary]
                        // where path is relative to the newly added node.
                        var props = diff[4];
                        for (var j=0; j < props.length; j++) {
                            var ppath = props[j][1];
                            var node_type = props[j][0];
                            var pnode = MirrorDom.Util.node_at_path(new_elem, ppath);
                            this.apply_props(props[j][2], null, pnode, ppath);
                        }
                        break;
                }
            } else {
                var new_elem = document.createTextNode(diff[3]);
                parent.appendChild(new_elem);
            }

        } else if (diff[0] == 'attribs') {
            // diff[3] = changed attributes
            // diff[4] = removed attributes
            var node = MirrorDom.Util.node_at_path(root, diff[2]);
            this.apply_attrs(diff[3], diff[4], node, diff[2]);
        } else if (diff[0] == 'props') {
            // diff[3] = changed properties
            // diff[4] = removed properties (may not exist)
            var removed = (diff.length == 4) ? diff[4] : null;
            var node = MirrorDom.Util.node_at_path(root, diff[2]);
            this.apply_props(diff[3], removed, node, diff[2]);
        } else if (diff[0] == 'deleted') {
            var node = MirrorDom.Util.node_at_path(root, diff[2]);
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
// Event handling
// ----------------------------------------------------------------------------
MirrorDom.Viewer.prototype.add_event_listener = function(event, callback) {
    if (this.event_listeners[event] == undefined) {
        this.event_listeners[event] = [];
    }
    this.event_listeners[event].push(callback);
}

MirrorDom.Viewer.prototype.fire_event = function(event, data) {
    if (this.event_listeners[event] == undefined) { return; }
    for (var i=0; i < this.event_listeners[event].length; i++) {
        this.event_listeners[event][i](data);
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
