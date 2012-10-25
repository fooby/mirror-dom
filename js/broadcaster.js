/**
 * MirrorDom broadcaster proof of concept
 *
 * Depends on jQuery (couldn't avoid it)
 */

var MirrorDom = MirrorDom === undefined ? {} : MirrorDom;

/**
 * MirrorDom Broadcaster class.
 *
 * This is a tree structure, with the root object corresponding to the
 * "primary" broadcaster iframe. Child objects will be created to correspond to
 * child iframes/windows, which themselves may have further child iframes.
 *
 */

/**
 * Constructor and entry point for MirrorDom.Broadcaster class.
 *
 * @param options       Dictionary of various options - see init()
 * @param parent        Reference to parent broadcaster object.
 */
MirrorDom.Broadcaster = function(options, parent_details) {

    // Reference to our iframe element where the action takes place.
    this.iframe = null;

    // Reference to the parent broadcaster (except for the top level iframe)
    if (parent_details != null) {
         // 'i' for iframe, 'w' for window, 'm' for main
        this.frame_type = parent_details["frame_type"];
         // Path of this broadcaster, relative to parent broadcaster's frame/window
        this.path_in_parent = parent_details["path_in_parent"];
        // Reference to parent broadcaster
        this.parent = parent_details["parent"];
        this.event_listeners = null;
    } else {
        this.frame_type = 'm';
        this.path_in_parent = [];
        this.parent = null;
        this.event_listeners = {};
    }

    // Mapping of path keys -> broadcaster object for child iframes
    // Paths converted to comma separated strings e.g. a node path of [1,2,4]
    // becomes "1,2,4" 
    this.child_iframes = {};

    // State
    this.cloned_dom = null;
    this.was_new_page_loaded = false;

    // Polling and comms (top level iframe only)
    this.sending = false;

    // Misc
    this.debug = false;

    // Initialise options
    this.init_options(options);
    
    // Attach load handler
    jQuery(this.iframe).on("load.mirrordom", jQuery.proxy(this.handle_load_page, this));
}

/**
 * Extract options from constructor arg
 *
 * @param options           Broadcaster options
 *
 *      - iframe:   An iframe object to track, otherwise we'll just use the
 *                  current document (which should not be used in practice,
 *                  only for testing/demonstration). Make sure it's the actual
 *                  element reference, and not something wrapped in a jQuery
 *                  object.
 *
 *                  Warning: Won't work for cross domain iframes.
 */
MirrorDom.Broadcaster.prototype.init_options = function(options) {
    // Transport mechanism
    if (options.push_method) {
        this.push_method = options.push_method;
    } else if (options.root_url) {
        var pusher = new MirrorDom.JQueryXHRPusher(options.root_url);
        this.push_method = jQuery.proxy(pusher, "push");
    }

    // Force the poll message to be sent even if no data we need to send
    this.force_poll = options.force_poll ? true : false;

    // Iframe MUST exist
    this.iframe = options.iframe;

    // Debug log messages
    this.debug = options.debug ? true : false;
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
MirrorDom.Broadcaster.prototype.go = function() {
    this.poll();
}


// ----------------------------------------------------------------------------
// Core logic
//
// Anything that updates the state variables
// (e.g. cloned_dom, child_iframe_broadcasters)
// should go here.
// ----------------------------------------------------------------------------

/**
 * The MAIN process, can be called at regular intervals or manually invoked.
 *
 * Returns the messages
 */
MirrorDom.Broadcaster.prototype.process_and_get_messages = function(messages) {
    // Ok, start preparing to generate a new set of messages from examining our
    // document:
    //
    // The data structure we'll send:
    // - messages:      List of messages for current window
    // 
    // "Messages" are representations of events and their data. e.g.:
    //
    // - Starting a new broadcaster session should transmit all the initial
    // html and element properties.
    //
    // - A change to the DOM should result in transmitting the relevant changes
    // of that particular branch of the tree
    //
    // - Loading a new page should transmit all the initial html of the new
    // page.
    //
    // Each message should be self contained such that applying a single
    // message should result in the receiver able to have a complete
    // reconstruction of the DOM at that point in time. This means we don't
    // split state across multiple messages.
    //
    // This doesn't apply to iframes though. Iframes are treated as seperate
    // documents and not as part of the same document state.
    //
    // e.g. Sending the initial html in one message and the element properties
    // in a second message is bad, because the DOM state after applying the
    // first message will be incomplete.

    // Don't do anything if the document is still loading
    var d = this.get_document_object();
    if (d.readyState != "complete") {
        this.log("Page is loading, skip poll");
        return;
    }

    if (this.is_new_frame()) {
        var data = this.start_full_document();
        this.add_message(messages, "new_instance", data);
        this.log("Sending new instance for document at " + this.get_frame_path().join(","));
        this.was_new_page_loaded = false;
    } else if (this.was_new_page_loaded) {
        var data = this.start_full_document();
        this.add_message(messages, "new_page", data);
        this.log("Sending new page for document at " + this.get_frame_path().join(","));
        this.was_new_page_loaded = false;
    } else {
        var diffs = this.get_diff();
        if (diffs.length > 0) {
            this.log("Sending " + diffs.length + " diffs for document at " + this.get_frame_path().join(","));
            this.add_message(messages, "diffs", {"diffs": diffs});
        }
    }

    // Recurse into iframes and get those messages
    for (var key in this.child_iframes) {
        var b = this.child_iframes[key]['broadcaster'];
        b.process_and_get_messages(messages);
    }

    return messages;
}

MirrorDom.Broadcaster.prototype.add_message = function(messages, type, data) {
    var path = this.get_frame_path();
    //var name = path.join(",");
    messages.push([path, type, data]);
}

/**
 * We throw out all our current state, rescan the entire document and
 * return new messages to reconstruct the document.
 *
 * @returns     Message style document dump 
 */
MirrorDom.Broadcaster.prototype.start_full_document = function() {
    // We're destroying our state
    this.destroy_child_iframes();

    // Iterate through the document and collect data (iterate once only)
    var doc_elem = this.get_document_element();

    // -------------------------------------------------------------------------
    // DOM iterator handler
    // -------------------------------------------------------------------------
    var cloned_root = null;
    var previous_cloned_node;
    var prop_diffs = [];

    // -------------------------------------------------------------------------
    // End DOM iterator handler
    // -------------------------------------------------------------------------
    var dom_iterator = new MirrorDom.DomIterator(doc_elem);

    // Apply our handling of new nodes
    dom_iterator.attach_handler(jQuery.proxy(this.find_iframes_from_dom_iterator, this));
    dom_iterator.attach_handler(this.collect_props_from_dom_iterator, prop_diffs);
    dom_iterator.attach_handler(jQuery.proxy(this.rewrite_targets_in_dom_iterator, this));
    results = dom_iterator.run();

    // Clone the DOM
    this.make_dom_clone();
    var html = this.get_document_data(doc_elem);
    var url = this.iframe.contentWindow.location.href;

    var iframe_paths = [];
    for (var i = 0; i < this.child_iframes.length; i++) {
        iframe_paths.append(this.child_iframes[i]['ipath']);
    }

    for (var i = 0; i < prop_diffs.length; i++) {
        prop_diffs[i].unshift("props");
    }

    var data = {
        "html":  html,
        "props": prop_diffs,
        "url":   url,
        "iframes": iframe_paths
    }

    return data;
} 

/**
 * Retrieve the diff and update the cloned dom
 */
MirrorDom.Broadcaster.prototype.get_diff = function() {
    var doc_elem = this.get_document_element();
    var diffs = this.diff_dom(doc_elem, this.cloned_dom);

    // Re-clone the dom if we found any changes
    if (diffs.length > 0) {
        this.make_dom_clone();
    }
    return diffs;
}

MirrorDom.Broadcaster.prototype.make_dom_clone = function(doc_elem) {
    doc_elem = doc_elem == null ? this.get_document_element() : doc_elem;
    this.cloned_dom = this.clone_dom(doc_elem);
}

// ----------------------------------------------------------------------------
// Event handling
// ----------------------------------------------------------------------------
MirrorDom.Broadcaster.prototype.handle_load_page = function() {
    this.log("Loaded new page at " + this.get_frame_path().join(",") + " !" );
    this.was_new_page_loaded = true;
    this.fire_event("on_page_load", {url: this.iframe.contentWindow.location.href});
    this.rewrite_link_targets();
}

/**
 * Try to avoid frame busting links which set target to _top
 */
MirrorDom.Broadcaster.prototype.rewrite_link_targets = function() {
    var iframe_name = this.iframe.name;
    var doc_elem = this.get_document_element();
    var links_forms = jQuery("[target='_top']", doc_elem);
    links_forms.attr("target", iframe_name);
    this.log("Rewrote " + links_forms.length + " link/form targets to \"" + iframe_name + "\"");
}

// ----------------------------------------------------------------------------
// Event handling
// ----------------------------------------------------------------------------
MirrorDom.Broadcaster.prototype.add_event_listener = function(event, callback) {
    if (this.event_listeners[event] == undefined) {
        this.event_listeners[event] = [];
    }
    this.event_listeners[event].push(callback);
}

MirrorDom.Broadcaster.prototype.fire_event = function(event, data) {
    if (this.event_listeners == undefined || this.event_listeners[event] == undefined ) { return; }
    for (var i=0; i < this.event_listeners[event].length; i++) {
        this.event_listeners[event][i](data);
    }
}

// ----------------------------------------------------------------------------
// Internal utility functions
// ----------------------------------------------------------------------------


MirrorDom.Broadcaster.prototype.get_frame_path = function() {
    // Build absolute path by iterating through parents
    var path = [];
    var p = this;
    while (p != null) {
        // Prepend parent's relative path and child type ('i' for iframe, 'w' for window)
        path = p.path_in_parent.concat([p.frame_type], path);
        p = p.parent;
    }

    // Comma-join path elements
    return path;
}

MirrorDom.Broadcaster.prototype.get_document_object = function() {
    return MirrorDom.Util.get_document_object_from_iframe(this.iframe);
}

MirrorDom.Broadcaster.prototype.get_document_element = function() {
    return this.get_document_object().documentElement;
}

MirrorDom.Broadcaster.prototype.is_new_frame = function() {
    return (!this.cloned_dom);
}

MirrorDom.Broadcaster.prototype.is_top_broadcaster = function() {
    return this.parent == null;
}

// ----------------------------------------------------------------------------
// Internal logic
// ----------------------------------------------------------------------------
/**
 * Top level broadcaster only
 */
MirrorDom.Broadcaster.prototype.poll = function() {
    if (this.parent != null) {
        throw new Error("Can't poll on child broadcasters");
    }

    // Check if we're still in the middle of sending/receiving another message
    if (this.sending) {
        this.log("Broadcaster: still sending...")
        return;
    }

    var messages = []
    this.process_and_get_messages(messages);

    if (this.force_poll || messages.length > 0) {
        // Grab iframes to inform the server which iframes are in fact still
        // active after these latest changes.
        var iframes = this.get_all_iframe_paths();
        this.push_method('send_update', {"messages": messages, "iframes": iframes});
    }
}

/**
 * Clean up when we no longer need the broadcaster object
 */
MirrorDom.Broadcaster.prototype.destroy = function() {
    // Unload child iframe broadcasters
    this.destroy_child_iframes();

    // Unload mirrordom events hooked up to the iframe
    //
    // Disabling because this doesn't quite work right (plus the iframes don't
    // exist at the point this is called)
    //jQuery(this.iframe).off(".mirrordom");
}


/**
 * Populate a list with all iframe paths
 *
 * @param paths     The list the populate
 *
 * No return value
 */
MirrorDom.Broadcaster.prototype.get_all_iframe_paths = function(paths) {
    if (paths === undefined) {
        paths = [];
    }
    paths.push(this.get_frame_path());
    for (var key in this.child_iframes) {
        this.child_iframes[key]["broadcaster"].get_all_iframe_paths(paths);
    }
    return paths;
}

/**
 * Remove all broadcaster references to our iframes (usually done when doing a
 * complete document re-processing)
 */
MirrorDom.Broadcaster.prototype.destroy_child_iframes = function() {
    for (var path in this.child_iframes) {
        var b = this.child_iframes[path]['broadcaster'];
        b.destroy();
    }

    this.child_iframes = {};
}

/**
 * Returns a copy of a DOM tree (can't really use DomIterator because it
 * doesn't fit the paradigm)
 */
MirrorDom.Broadcaster.prototype.clone_dom = function(root) {
    var startTime = new Date().getTime();
    var node = root;
    var cloned_node = this.clone_node(root, true);
    var cloned_root = cloned_node;
    while (true) {
        if (node.firstChild) {
            node = node.firstChild;
            cloned_node.firstChild = this.clone_node(node, true);
            cloned_node.firstChild.parentNode = cloned_node;
            cloned_node = cloned_node.firstChild;
        } else if (node.nextSibling) {
            node = node.nextSibling;
            cloned_node.nextSibling = this.clone_node(node, true);
            cloned_node.nextSibling.parentNode = cloned_node.parentNode;
            cloned_node = cloned_node.nextSibling;
        } else {
            while (!node.nextSibling) {
                if (node === root) {
                    return cloned_root;
                }
                node = node.parentNode;
                cloned_node = cloned_node.parentNode;
            }
            node = node.nextSibling;
            cloned_node.nextSibling = this.clone_node(node, true);
            cloned_node.nextSibling.parentNode = cloned_node.parentNode;
            cloned_node = cloned_node.nextSibling;
        }
    }
    // unreachable
    return null;
};

/**
 * Extract relevant data from the node
 */
MirrorDom.Broadcaster.prototype.clone_node = function(node, include_properties) {
    // deep copy.
    var clone = {
        'attributes': {},
        'nodeName':   node.nodeName,
        'nodeType':   node.nodeType,
        'nodeValue':  node.nodeValue,
        'namespaceURI':  node.namespaceURI
    };

    if (node.attributes) {
        for (var i=0; i < node.attributes.length; i++) {
            var attrib = node.attributes[i];
            // IE thing 1
            if (attrib.name in MirrorDom.Util.IGNORE_ATTRIBS) { continue; }
            // IE thing 2
            if (attrib.specified) {
                clone.attributes[attrib.name] = attrib.value;
            }
        }
    }

    if (include_properties) {
        var props = MirrorDom.Util.get_properties(node);
        if (props != null) {
            clone.props = props;
        }
    }

    return clone;
};

/**
 * Start tracking a newly discovered iframe with a child Broadcaster object
 */
MirrorDom.Broadcaster.prototype.register_new_iframe = function(iframe, ipath) {

    this.log("Registering new iframe at " + ipath + "!");
    var key = ipath.join(",");
    if (key in this.child_iframes) {
        throw new Error("Trying to add new iframe which already exists at [" + key + "]");
    }

    var parent_details = {
        'parent': this,
        'frame_type': 'i', // i for iframe
        'path_in_parent': ipath
    }

    var options = {
        'iframe': iframe,
        'debug': this.debug
    }

    var iframe_broadcaster = new MirrorDom.Broadcaster(options, parent_details);

    this.child_iframes[key] = {
        'ipath': ipath,
        'broadcaster': iframe_broadcaster
    };
}

/**
 * Get the current document so we can replicate it. Hopefully we can just use
 * innerHTML...
 */
MirrorDom.Broadcaster.prototype.get_document_data = function(doc_elem) {
    doc_elem = doc_elem == null ? this.get_document_element() : doc_elem;
    return ['<html>', doc_elem.innerHTML, '</html>'].join('');
};

// ----------------------------------------------------------------------------
// DOM diffing (messy, sorry)
// ----------------------------------------------------------------------------
MirrorDom.Broadcaster.prototype.diff_dom = function(dom_root, cloned_root) {
    // ipath contains our current position in the tree. This is basically a
    // list of node offsets. Each entry in the list corresponds to a level of
    // the tree, with the value corresponding the 0-based offset of the node
    // relative to its siblings.
    //
    // Example:
    // In the following document:
    //
    // <html>
    //   <head>...</head>
    //   <body>
    //     <div>...</div>
    //     <a>...</a>
    //     <p>...</p>
    //     <li>...</li>
    //   </body>
    // </html>
    //
    // [0, 1, 3] represents the path to the <li> element.
    //
    // 0 = The <html> element (the first entry will always be 0)
    // 1 = The 2nd element under html, in this case <body>
    // 3 = The 4th element under body, in this case <li>
    //
    // Note: Empty text nodes are ignored, but non-empty text nodes are
    // included in the index offsets.
    
    var ipath = [];
    var diffs = [];

    // We have an "actual" and "cloned" tree being traversed in lockstep:
    // Actual: The current DOM being viewed in the browser
    // Cloned: A representation of the previous state of the DOM at
    //         the time we did our last diff.
 
    // Used to indicate when we've finished traversing a node's children and
    // need to go back up.
    var ascended_parent = false;

    // Which nodes are being compared at the start of each iteration
    var node = dom_root;
    var cnode = cloned_root;

    // Keep references of the current node's parents
    var node_parent = null;
    var cnode_parent = null;
   
    while (true) {
        if (ascended_parent) {
            // Don't do node comparison, just traverse onto next sibling
            ascended_parent = false;
        } else if (cnode == null) {

            // SCENARIO 1: One or more new nodes added, all them all to the diff
            while (node) {
                this.handle_diff_added_node(diffs, ipath, node);
                // Move onto next node
                node = MirrorDom.Util.apply_ignore_nodes(node.nextSibling);
                ipath[ipath.length-1]++;
            }
            // node and cnode should be null at this point (causing parent ascent)
        } else if (node == null) {
            // SCENARIO 2: A node was removed recently
            this.handle_diff_delete_nodes(diffs, ipath, cnode);
            cnode = null;
        } else {
            // SCENARIO 3: We have two nodes we need to compare
            // Compare the node tagNames
            var structure_changed = this.compare_nodes(ipath, node, cnode);

            if (!structure_changed) {
                this.handle_diff_node_attributes(diffs, ipath, node, cnode);
                this.handle_diff_node_properties(diffs, ipath, node, cnode);

                // The nodes appear to be the same, let's descend into child
                // nodes if they exist
                if (node.firstChild != null || cnode.firstChild != null) {
                    // At least one of the nodes has children, so we'll descend
                    node_parent = node;
                    cnode_parent = cnode;
                    node = MirrorDom.Util.apply_ignore_nodes(node.firstChild);
                    cnode = MirrorDom.Util.apply_ignore_nodes(cnode.firstChild);

                    // Add 0 onto the ipath path to represent visiting the
                    // first child of the current node
                    ipath.push(0);
                    continue
                }

            } else {
                // Node has visibly changed. The "changed" node might indicate
                // an inserted/deleted node. We'll just delete and recreate all
                // the siblings to the right of this node.
                
                // Handle delete messages for the nodes
                cnode_ipath = ipath.slice();
                
                this.handle_diff_delete_nodes(diffs, cnode_ipath, cnode);
                    
                // Now handle add messages to recreate all the nodes
                while (node) {
                    this.handle_diff_added_node(diffs, ipath, node);
                    node = MirrorDom.Util.apply_ignore_nodes(node.nextSibling);
                    ipath[ipath.length-1]++;
                }
            }
        }
        
        // Oh look, we've reached the root node, let's finish there
        if (node === dom_root) {
            break;
        }

        if (node != null && cnode != null) {
            // Proceed onto next sibling if both nodes existed
            node = MirrorDom.Util.apply_ignore_nodes(node.nextSibling);
            cnode = MirrorDom.Util.apply_ignore_nodes(cnode.nextSibling);

            // Increase the last ipath element to represent the next sibling
            ipath[ipath.length-1]++;
        } else {
            // Parent traversal since we're done with siblings
            node = node_parent;
            cnode = cnode_parent;
            node_parent = node.parentNode;
            cnode_parent = cnode.parentNode;

            // Pop last item off path to represent going back up the tree
            ipath.pop();
            
            // Notiy that we're revisiting the parent for the second time (i.e.
            // we're ready to move onto the siblings)
            ascended_parent = true;
        }
    }
    return diffs;
}
/**
 * Compares the tagname, nodetype and attributes. Dumps difference information
 * into diffs param.
 *
 * Note: dnode (aka actual node) always exists, cnode may not exist (indicating
 * a recently added node)
 *
 * Returns true if structurally different, false if same
 */
MirrorDom.Broadcaster.prototype.compare_nodes = function(ipath, dnode, cnode) {
    if (dnode.nodeName != cnode.nodeName || dnode.nodeType != cnode.nodeType || 
            dnode.nodeValue != cnode.nodeValue) {
        return true;
    }
    return false;
}

/**
 * Called at the top of an added node structure - not called on child nodes,
 * but we're about to iterate through them anyway.
 */
MirrorDom.Broadcaster.prototype.handle_diff_added_node = function (diffs, ipath, node) {
    ipath = ipath.slice();
    switch (node.nodeType) {
        case 1:
            // ELEMENT
            var dom_iterator = new MirrorDom.DomIterator(node, ipath);
            var prop_diffs = [];
            // We've detected a new Element node. We want to continue iterating
            // through the added node's structure.
            // 1) Check if there's any iframes that we need to keep track of
            dom_iterator.attach_handler(jQuery.proxy(this.find_iframes_from_dom_iterator, this));
            // 2) Collect node properties relative to the newly added node
            dom_iterator.attach_handler(this.collect_props_from_dom_iterator, prop_diffs);
            dom_iterator.attach_handler(jQuery.proxy(this.rewrite_targets_in_dom_iterator, this));
            dom_iterator.run();

            // Ok, add the new node
            var html = MirrorDom.Util.get_outerhtml(node);
            var type = MirrorDom.Util.get_node_doc_type(node); // svg or html
            diffs.push(['node', type, ipath, html, prop_diffs]);
            break;
        case 3:
            // TEXT
            var type = MirrorDom.Util.get_node_doc_type(node); // svg or html
            diffs.push(['text', type, ipath, MirrorDom.Util.get_text_node_content(node)]);
            break;
    }
}


/**
 * Called at the top of an deleted node structure (for cloned nodes).
 * Note: When this is called, the node and ALL siblings to the right have been
 * deleted.
 *
 * @param cnode             Node cloned in clone_node() (not an actual DOM node)
 */
MirrorDom.Broadcaster.prototype.handle_diff_delete_nodes = function(diffs, ipath, cnode) {
    var type = MirrorDom.Util.get_node_doc_type(cnode); // html or svg
    diffs.push(['deleted', type, ipath.slice()]);
    //diffs.push(['deleted', type, ipath.slice(), cnode.nodeName, cnode.nodeValue]);
    ipath = ipath.slice();
    // Scan for iframes which have been deleted
    while (cnode) {
        for (var key in this.child_iframes) {
            var child_iframe_ipath = this.child_iframes[key]['ipath'] ;
            if (MirrorDom.Util.is_inside_path(child_iframe_ipath, ipath)) {
                // Remove iframe object
                this.log("Removing iframe at " + child_iframe_ipath + "! (Because of deleted node " + ipath + ")");
                this.child_iframes[key]['broadcaster'].destroy();
                delete this.child_iframes[key];
            }
        }

        // Move to next sibling
        cnode = MirrorDom.Util.apply_ignore_nodes(cnode.nextSibling);
        ipath[ipath.length-1]++;
    }
}

/**
 */
MirrorDom.Broadcaster.prototype.handle_diff_node_properties = function(diffs, ipath, dnode, cnode) {    
    var changed_props = {};
    var removed_props = [];
    var diff = false;

    // include properties that aren't reflected as DOM attributes
    var property_lookup_list = MirrorDom.Util.get_property_lookup_list(dnode);
    for (i=0; i < property_lookup_list.length; i++) {
        var prop_key = property_lookup_list[i][0];
        var prop_lookup = property_lookup_list[i][1];
        var dprop_result = MirrorDom.Util.get_property(dnode, prop_lookup);
        var dprop_found = dprop_result[0];
        var dprop_value = dprop_result[1];

        var cprop_found = cnode.props != null ? prop_key in cnode.props : false;
        var cprop_value = cnode.props != null ? cnode.props[prop_key] : null;

        if (dprop_found && !cprop_found) {
            if (dprop_value == "") {
                // Yeah, it's not really worthy of keeping is it
                continue;
            }
            // Property added
            changed_props[prop_key] = dprop_value;          
            diff = true;
        } else if (!dprop_found && cprop_found) {
            // Property removed
            removed_props.push(prop_key);
            diff = true;
        } else if (cprop_found && dprop_found && dprop_value != cprop_value) {
            // Property changed
            changed_props[prop_key] = dprop_value;          
            diff = true;
        }
    }

    if (diff) {
        var type = MirrorDom.Util.get_node_doc_type(dnode); // html or svg
        diffs.push(['props', type, ipath.slice(), changed_props, removed_props]);
    }
}


MirrorDom.Broadcaster.prototype.handle_diff_node_attributes = function(diffs, ipath, dnode, cnode) {    
    var diff_attribs = {};
    var dattribs = {};

    var cattribs = cnode.attributes;
    var diff = false;
    var key;
    var attrib;

    var changed_attribs = {}
    var removed_attribs = [];

    if (dnode.attributes == null) {
        //if (cnode.attributes != null) {
        //    throw new Error("cnode has attributes but dnode doesn't?");
        //}
        return;
    }

    // convert .attributes map to an object dict
    for (var i = 0; i < dnode.attributes.length; i++) {

        // For Internet Explorer: style attrib is always null
        if (dnode.attributes[i].name in MirrorDom.Util.IGNORE_ATTRIBS) {
            continue;
        }

        // IE hack for "specified" attributes (where .attributes contains
        // the entire set of possible attributes)
        if (!dnode.attributes[i].specified) { continue; }
        var dattrib_name = dnode.attributes[i].name;
        var dattrib_value = dnode.attributes[i].nodeValue;
        if (dattrib_value != cattribs[dattrib_name]) {
            // Either it's been changed or it was added
            changed_attribs[dattrib_name] = dattrib_value;
            diff = true;
        }
    }

    // Any attribs been removed?
    // Note: cnode is just a straight up associative dict object (see
    // clone_node()).
    for (var key in cnode.attributes) {
        
        // For Internet Explorer: style attrib is always null
        if (key in MirrorDom.Util.IGNORE_ATTRIBS) {
            continue;
        }

        // Note: Because of clone_node's attribute copying, the attribute
        // values are actually attribute nodes. That might not be such a good
        // thing? Maybe I'll have to fix that later
        if (!cnode.attributes[key].specified) { continue; }
        //var cattrib_name = cnode.attributes[key].name;
        var cattrib_value = cnode.attributes[key].nodeValue;
        if (dnode.attributes[key] == undefined) {
            removed_attribs.push(cattrib_name);
            diff = true;
        }
    }

    if (diff) {
        var type = MirrorDom.Util.get_node_doc_type(dnode); // html or svg
        diffs.push(['attribs', type, ipath.slice(), changed_attribs, removed_attribs]);
    }
};

// ----------------------------------------------------------------------------
// Debug functions
// ----------------------------------------------------------------------------
/**
 * Debug logging
 */
MirrorDom.Broadcaster.prototype.log = function(msg) {
    if (this.debug && window.console && console.log) {
        console.log(msg);
    }
}

// ============================================================================
// DOM iterator class
// ============================================================================

/**
 * @param base_ipath    If iterating through a subset of a document, then
 *                      base_ipath is the path to the root.
 *                      Will be passed to the handlers along with the relative
 *                      path.
 */
MirrorDom.DomIterator = function(root, base_ipath) {
    this.root = root;
    this.base_ipath = base_ipath === undefined ? [] : base_ipath;
    this.handlers = [];
}

/**
 * @param handler           A callback which accepts the following arguments:
 *                          (node, base_ipath, ipath, data)
 * @param data              A mutable data object to pass back to the handler,
 *                          or null if not using
 */
MirrorDom.DomIterator.prototype.attach_handler = function(handler, data) {
    this.handlers.push([handler, data]);
}

MirrorDom.DomIterator.prototype.log = function(msg) {
    if (window.console && console.log) {
        console.log(msg); 
    }
}

/**
 * Returns the next node.
 */
MirrorDom.DomIterator.prototype.run = function() {
    var node = this.root;
    var ipath = [];
    var ascending = false;
    var results = this.results;

    while (true) {
        if (!ascending) {
            this.apply_handlers(node, ipath.slice());

            // Traverse into child
            var next_child = node.firstChild ?
                MirrorDom.Util.apply_ignore_nodes(node.firstChild) : null;
            if (next_child != null) {
                node = next_child;
                ipath.push(0);
                continue;
            }
        } else {
            ascending = false;
        }

        if (node === this.root) {
            return;
        }

        // No child, try traverse into sibling
        var next_sibling = MirrorDom.Util.apply_ignore_nodes(node.nextSibling);
        if (next_sibling != null) {
            node = next_sibling;
            ipath[ipath.length-1]++;
        } else {
            // Reached the end of siblings, ascend parent or terminate
            node = node.parentNode;
            ipath.pop();
            ascending = true;
        }
    }
}

MirrorDom.DomIterator.prototype.apply_handlers = function(node, ipath) {
    for (var i=0; i < this.handlers.length; i++) {
        var f = this.handlers[i][0];
        var data = this.handlers[i][1];
        f(node, this.base_ipath, ipath, data);
    }
}

// ----------------------------------------------------------------------------
// DOM iterator helpers
// ----------------------------------------------------------------------------
/**
 * @param data      Data should be an array
 */
MirrorDom.Broadcaster.prototype.collect_props_from_dom_iterator = function(node, base_ipath, ipath, data) {
    if (node.nodeType == 1) {
        var props = MirrorDom.Util.get_properties(node);
        if (props != null) {
            var type = MirrorDom.Util.get_node_doc_type(node); // html or svg
            data.push([type, ipath.slice(), props]);
        }
    }
}

/**
 * When encountering a new node, see if it's an iframe and if so, register it.
 *
 * To be used with the DomIterator class.
 */
MirrorDom.Broadcaster.prototype.find_iframes_from_dom_iterator = function(node, base_ipath, ipath) {
    var full_path = base_ipath.concat(ipath);
    if (node.nodeName.toLowerCase() == 'iframe') {
        this.register_new_iframe(node, full_path);
    }
}

MirrorDom.Broadcaster.prototype.rewrite_targets_in_dom_iterator = function(node, base_ipath, ipath) {
    var node = jQuery(node);
    //this.log("Node: " + MirrorDom.Util.describe_node(node[0]));
    if (node.attr("target") == "_top") {
        var iframe_name = this.iframe.name;
        node.attr("target", iframe_name);
        this.log("Rewrote a target attribute while iterating");
    }
}

// ----------------------------------------------------------------------------
// Tranport
// ----------------------------------------------------------------------------

/* JQuery-XHR implementation of server push - we just POST all the data to
 * root_url + the method name */
 
MirrorDom.JQueryXHRPusher = function(root_url) {
    this.root_url = root_url;
};

/**
 * @param args      Either a mapping or a string
 */
MirrorDom.JQueryXHRPusher.prototype.push = function(method, args, callback) {
    for (var k in args) {
        if (jQuery.isPlainObject(args[k]) || jQuery.isArray(args[k])) {
            args[k] = JSON.stringify(args[k]);
        }
    }

    jQuery.post(this.root_url + method, args, function(result) {
        if (callback) callback(JSON.parse(result));
    });
};
