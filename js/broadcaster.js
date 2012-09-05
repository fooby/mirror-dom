/**
 * MirrorDOM broadcaster proof of concept
 */

var MirrorDom = MirrorDom === undefined ? {} : MirrorDom;

MirrorDom.Broadcaster = function(options) {
    this.sending = false;
    this.cloned_dom = null;
    this.interval_event = null;
    this.name = null;
    this.new_page_loaded = false;
    this.iframe = null;
    this.init(options);
}

// Property names
MirrorDom.Broadcaster.prototype.PROPERTY_NAMES = ["disabled", "value", "checked", "style.cssText", "className"];
MirrorDom.Broadcaster.prototype.IGNORE_ATTRIBS = {"style": null};
MirrorDom.Broadcaster.prototype.PROPERTY_LOOKUP = 
        MirrorDom.Util.process_property_paths(MirrorDom.Broadcaster.prototype.PROPERTY_NAMES);

// Gets the jQuerified iframe object
MirrorDom.Broadcaster.prototype.get_iframe = function(node) {
    return jQuery(this.iframe);
}

MirrorDom.Broadcaster.prototype.get_document_object = function() {
    return MirrorDom.Util.get_document_object_from_iframe(this.iframe);
}

MirrorDom.Broadcaster.prototype.get_document_element = function() {
    return this.get_document_object().documentElement;
}

MirrorDom.Broadcaster.prototype.clone_node = function(node, include_properties) {
    // deep copy.
    var clone = {};
    clone.nodeName = node.nodeName;
    clone.attributes = {};
    clone.nodeType = node.nodeType;
    if (node.attributes) {
        for (var i=0; i < node.attributes.length; i++) {
            var attrib = node.attributes[i];

            // IE thing 1
            if (attrib.name in this.IGNORE_ATTRIBS) {
                continue;
            }

            // IE thing 2
            if (attrib.specified) {
                clone.attributes[attrib.name] = attrib.value;
            }
        }
    }

    // include properties that aren't reflected as DOM attributes
    //var prop_names = MirrorDom.Broadcaster.PROP_NAMES;

    if (include_properties) {
        clone.props = {};
        for (i=0; i < this.PROPERTY_LOOKUP.length; i++) {
        //for (i=0; i < prop_names.length; i++) {
            //var name = prop_names[i];
            //if (name in node) {
            //    clone.attributes[name] = node[name];
            //}
            var prop_text = this.PROPERTY_LOOKUP[i][0];
            var prop_lookup = this.PROPERTY_LOOKUP[i][1];
            var prop_result = MirrorDom.Util.get_property(node, prop_lookup);
            var prop_found = prop_result[0];
            var prop_value = prop_result[1];
            if (prop_found) {
                // MirrorDom.Util.set_property(clone, prop_lookup, prop_value, true);
                clone.props[prop_text] = prop_value;
                
            }
        }
    }

    clone.nodeValue = node.nodeValue;

    return clone;
};

MirrorDom.Broadcaster.prototype.add_node_diff = function(diffs, ipath, node) {
    if (node.nodeType == 1) {
        // element        
        diffs.push(['node', ipath.slice(), node.innerHTML, 
                this.clone_node(node), 
                //this.get_nodes_with_properties(node)]);
                this.get_property_diffs(node)
        ]);
    } else if (node.nodeType == 3) {
        // text node
        diffs.push(['text', ipath.slice(), node.textContent]);
    } else {
        // not a fragment we care about 
        return;
    }
};

/*node_at_path = function(root, ipath) {
    var node = root;
    for (var i=0; i < ipath.length; i++) {
        node = node.firstChild;
        for (var j=0; j < ipath[i]; j++) {
            node = node.nextSibling;            
        }
    }
    return node;
};*/


/**
 * Compares the tagname, nodetype and attributes. Dumps difference information
 * into diffs param.
 *
 * Note: dnode (aka actual node) always exists, cnode may not exist (indicating
 * a recently added node)
 *
 * Returns true if structurally different, false if same
 */
MirrorDom.Broadcaster.prototype.compare_nodes = function(diffs, ipath, dnode, cnode) {
    if (!cnode) {
        // Corresponding node doesn't exist, this means the current document
        // acquired a new node.
        this.add_node_diff(diffs, ipath, dnode);        
        return true;
    }

    if (dnode.nodeName != cnode.nodeName || dnode.nodeType != cnode.nodeType || 
            dnode.nodeValue != cnode.nodeValue) 
    {
        // pretty different, replace the node
        this.add_node_diff(diffs, ipath, dnode);
        return true;
    }

    this.compare_node_attributes(diffs, ipath, dnode, cnode);
    this.compare_node_properties(diffs, ipath, dnode, cnode);
}

MirrorDom.Broadcaster.prototype.compare_node_attributes = function(diffs, ipath, dnode, cnode) {    
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
        return false;
    }

    // convert .attributes map to an object dict
    for (var i = 0; i < dnode.attributes.length; i++) {

        // For Internet Explorer: style attrib is always null
        if (dnode.attributes[i].name in this.IGNORE_ATTRIBS) {
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
        if (key in this.IGNORE_ATTRIBS) {
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
        diffs.push(['attribs', ipath.slice(), changed_attribs, removed_attribs]);
        return true;
    }

    return false;
};

/**
 * @param cnode         Node cloned in clone_node() (not an actual DOM node)
 */
MirrorDom.Broadcaster.prototype.compare_node_properties = function(diffs, ipath, dnode, cnode) {    
    var changed_props = {};
    var removed_props = [];
    var diff = false;

    // include properties that aren't reflected as DOM attributes
    for (i=0; i < this.PROPERTY_LOOKUP.length; i++) {
        var prop_text = this.PROPERTY_LOOKUP[i][0];
        var prop_lookup = this.PROPERTY_LOOKUP[i][1];
        var dprop_result = MirrorDom.Util.get_property(dnode, prop_lookup);
        var dprop_found = dprop_result[0];
        var dprop_value = dprop_result[1];

        var cprop_found = prop_text in cnode.props;
        var cprop_value = cnode.props[prop_text];

        if (dprop_found && !cprop_found) {
            // Property added
            changed_props[prop_text] = dprop_value;          
            diff = true;
        } else if (!dprop_found && cprop_found) {
            // Property removed
            removed_props.push(prop_text);
            diff = true;
        } else if (dprop_value != cprop_value) {
            // Property changed
            changed_props[prop_text] = dprop_value;          
            diff = true;
        }
    }

    if (diff) {
        diffs.push(['props', ipath.slice(), changed_props, removed_props]);
        return true;
    }

    return false;
}

MirrorDom.Broadcaster.prototype.diff_dom2 = function(dom_root, cloned_root) {
    var startTime = new Date().getTime();

    // istack contains our current position in the tree. This is basically a
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
    // (In this example assume text nodes don't exist)
    //
    // [0, 1, 3] represents the path to the <li> element.
    //
    // 0 = The <html> element (the first entry will always be 0)
    // 1 = The 2nd element under html, in this case <body>
    // 3 = The 4th element under body, in this case <li>
    //
    var istack = [];

    // Diff directives to transmit to the mirrordom server 
    var diffs = [];

    // We have an "actual" and "cloned" tree being traversed in lockstep:
    // Actual: The current DOM being viewed in the browser
    // Cloned: A representation of the previous state of the DOM at
    //         the time we did our last diff.


    // Used to indicate when we've finished traversing a node's children and
    // need to go back up.
    var ascend_parent = false;

    // Which nodes are being compared at the start of each iteration
    var node = dom_root;
    var cnode = cloned_root;

    // Keep references of the current node's parents
    var node_parent = null;
    var cnode_parent = null;
   
    while (true) {
        // At the start of each loop we have to compare the values of node and
        // cnode. "node" represents a node from the actual tree, and "cnode"
        // represents a node from the cloned tree.  Initially the node and
        // cnodes are set to the root of their respective trees.
        //
        // We're doing a depth-first search using firstChild, nextSibling and
        // parentNode to traverse instead of more traditional stack based
        // techniques.
        //
        // At the end of the loop, "node" and "cnode" are traversed onto the
        // next nodes that we need to compare, at which point we start a new
        // iteration. 

        // Step 1 when visiting a node is to compare the node's tagNames and
        // attributes. 
        // Step 2 is to iterate through the node's children
        // Step 3 is to traverse onto the next sibling - or, if no more
        // siblings, then up to the parent.

        // Let's compare the nodes. The following scenarios are possible:
        // 1) "cnode" does not exist, but "node" does. This indicates recently
        //    added nodes.
        // 2) "node" does not exist, but "cnode" does. This indicates recently
        //    removed nodes.
        // 3) Both "cnode" and "node" exist, so we're going to have to compare
        //    their values and traverse children.
        //
        // 4) Not really a scenario, but this occurs when we've just finished
        //    traversing the nodes' children and need to resume traversing
        //    siblings.
        if (ascend_parent) {
            // Senario 4) We've just completed an ascent from this node's children.
            // At this point there's nothing to be done except traverse onto
            // the sibling (or continue ascending if no more siblings)
            //
            // Traversing code is later in this loop logic.
            ascend_parent = false;
        } else if (cnode == null) {
            // Scenario 1) A node was added recently
            while (node) {
                // Add a wholesale copy of the node and its children
                this.add_node_diff(diffs, istack, node);

                // Move to next node
                node = MirrorDom.Util.apply_ignore_nodes(node.nextSibling);

                // Increase last ipath element to represent next sibling. 
                istack[istack.length-1]++;
            }
            // Finished with this node and its siblings, ascend back up
            ascend_parent = true;
        } else if (node == null) {
            // Scenario 2) A node was removed recently
            // Add message to delete the node and all its children
            diffs.push(['deleted', istack.slice()]);
            // Finished with this node and its siblings, ascend back up
            ascend_parent = true;
        } else {
            // Scenario 3) We have nodes we need to compare
            // Compare the node tagNames, attributes, properties
            var changed = this.compare_nodes(diffs, istack, node, cnode);
            if (!changed) {
                // The nodes appear to be the same, let's compare the children
                if (node.firstChild != null || cnode.firstChild != null) {
                    // At least one of the nodes has children, so we'll descend
                    node_parent = node;
                    cnode_parent = cnode;
                    node = MirrorDom.Util.apply_ignore_nodes(node.firstChild);
                    cnode = MirrorDom.Util.apply_ignore_nodes(cnode.firstChild);

                    // Add 0 onto the istack path to represent visiting the
                    // first child of the current node
                    istack.push(0);
                    continue
                }
            }
            else {
                // Special case: The nodes are different, but compare_nodes()
                // has basically added an entire diff directive to reconstruct
                // this node in the viewers, so no further action is necessary.
                // We'll move onto the next node.
            }
        }

        // Perform traversal onto next sibling or parent. If ascend_parent
        // was set, that means we already know we want to go back up and we'll
        // skip this bit.
        if (!ascend_parent) {

            // Move onto the next sibling
            node = MirrorDom.Util.apply_ignore_nodes(node.nextSibling);
            cnode = MirrorDom.Util.apply_ignore_nodes(cnode.nextSibling);

            // Increase the last ipath element to represent the next sibling
            istack[istack.length-1]++;

            if (node == null && cnode == null) {
                // No siblings remaining, go back up to the parent node.                     
                ascend_parent = true;
            }
        }

        if (ascend_parent) {
            // Test if we're already at the root node and hence have completed
            // the diff.
            //
            // Note: The parent of the actual HTML root is the Document node,
            // while the parent of the cloned HTML node is null. So
            // realistically, we are only checking for cnode_parent == null
            if (node_parent == null || cnode_parent == null) {
                // We're back at the root element, so terminate the loop
                break;
            }

            // Parent traversal
            node = node_parent;
            cnode = cnode_parent;
            node_parent = node.parentNode;
            cnode_parent = cnode.parentNode;

            // Pop the last item off our node path to represent going back up
            // the tree
            istack.pop();
            
            // NOTE: We need to leave ascend_parent as true as an indicator
            // that we've finished iterating through a node's children in the
            // next iteration.
        }
    }
    return diffs;
}

/**
 * Force obtain all css inline styles. This occurs in two situations:
 *
 * After the initial HTML dump, which may (IE) or may not (Firefox) represent
 * updated CSS information.
 *
 * When obtaining the diff for a new/changed node, where we want to transport
 * the relative properties within that tree.
 *
 * @param node      The node to diff from. If null, use document element.
 *
 * @returns         A list of diffs. The node paths in the diffs will be
 *                  relative to the node param.
 */
MirrorDom.Broadcaster.prototype.get_property_diffs = function(node) {
    if (node == null) {
        node = this.get_document_element();
    }
    var ipath = [];
    var diffs = [];

    // Indicates whether we've just finished visiting this node's children 
    // and need to traverse to sibling 
    var ascended_parent = false;

    while (true) {

        if (!ascended_parent) {

            // Element nodes only
            if (node.nodeType == 1) {
                // Let's go check the node
                var changed_props = {}
                var diff = false;
                for (var i = 0; i < this.PROPERTY_LOOKUP.length; i++) {
                    var prop_text = this.PROPERTY_LOOKUP[i][0];
                    var prop_lookup = this.PROPERTY_LOOKUP[i][1];
                    var prop_result = MirrorDom.Util.get_property(node, prop_lookup);
                    var prop_found = prop_result[0];
                    var prop_value = prop_result[1];
                    if (prop_found && (prop_value != "" && prop_value != null)) {
                        changed_props[prop_text] = prop_value;
                        diff = true;
                    }
                }

                if (diff) {
                    diffs.push(['props', ipath.slice(), changed_props, null]);
                }
            }

            // Traverse into child
            var next_child = node.firstChild ? MirrorDom.Util.apply_ignore_nodes(node.firstChild) : null;
            if (next_child != null) {
                node = next_child;
                ipath.push(0);
                continue;
            }

        } else {
            // We've just ascended, we want to traverse
            ascended_parent = false;
        }

        // Try traverse into sibling
        var next_sibling = MirrorDom.Util.apply_ignore_nodes(node.nextSibling);
        if (next_sibling != null) {
            node = next_sibling;
            ipath[ipath.length-1]++;
        } else {
            // Reached the end of siblings, ascend parent or terminate
            node = node.parentNode;
            ipath.pop();
            
            // Oh look, we've reached the end
            if (ipath.length == 0) {
                break;
            }

            ascended_parent = true;
        }
    }

    return diffs;
}

/**
 * Returns a copy of a DOM tree
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
 * Get the current document so we can replicate it
 */
MirrorDom.Broadcaster.prototype.get_document_data = function() {
    var doc_elem = this.get_document_element();
    this.cloned_dom = this.clone_dom(doc_elem);
    var html_node = doc_elem;
    
    // for first snapshot, just send html
    return html_node.innerHTML;
};

MirrorDom.Broadcaster.prototype.get_diff = function() {
    var d = this.get_document_object();

    //debugger;
    //var diff = this.diff_dom(d.documentElement, this.cloned_dom);
    var diff = this.diff_dom2(d.documentElement, this.cloned_dom);
    
    if (diff.length) {
        // update the cloned dom as we detected changes.
        // todo: update cloned dom using diff!
        this.cloned_dom = this.clone_dom(d.documentElement);
    }

    return diff;
};

MirrorDom.Broadcaster.prototype.send_new_window = function() {
    var iframe = this.get_iframe();
    var src = iframe.attr('src');

    var self = this;
    this.pusher.push("new_window", {
        "html": this.get_document_data(),
        
        // The HTML may not reflect the current properties and CSS
        "props": this.get_property_diffs(null),
        "url": src
    },
    function(window_id) {
        // window.name persists across page loads
        self.name = window_id;
        self.sending = false;
    });
};

MirrorDom.Broadcaster.prototype.send_new_page_loaded = function() {
    var iframe = this.get_iframe();
    var src = iframe.attr('src');

    // URL has changed
    this.pusher.push("reset", {
        "window_id": this.name,
        "html": this.get_document_data(),
        
        // The HTML may not reflect the current properties and CSS
        "props": this.get_property_diffs(null),
        "url": src
    });
}

MirrorDom.Broadcaster.prototype.is_new_window = function() {
    return (!this.cloned_dom);
}

MirrorDom.Broadcaster.prototype.handle_load_page = function() {
    this.new_page_loaded = true;        
}

MirrorDom.Broadcaster.prototype.poll = function() {
    if (this.sending) {
        console.log("still sending...")
        return;
    }

    console.log("POL!")

    if (this.is_new_window()) {
        this.send_new_window();
    } else
    if (this.new_page_loaded) {
        this.new_page_loaded = false;
        this.send_new_page_loaded();

        //if (this.is_new_window()) {
        //    this.send_new_window();
        //} else {
        //    this.send_new_page_loaded();
        //}
    } else if (!this.is_new_window()) {
        // send difference between now and the cloned dom
        var diff = this.get_diff();
        var self = this;
        if (diff.length) {
            this.sending = true;
            this.pusher.push("add_diff", {
                "window_id": this.name,
                "diff": diff
            }, 
            function() {
                self.sending = false;
            });
        }
    }
}

/**
 * Entry point
 */
MirrorDom.Broadcaster.prototype.start = function() {
    var self = this;
    console.log("Poll interval: " + this.poll_interval);

    // Attach load handler
    var iframe = this.get_iframe();
    iframe.load(jQuery.proxy(this.handle_load_page, this));

    this.interval_event = window.setInterval(function() {
        self.poll();
    }, this.poll_interval);
};

MirrorDom.Broadcaster.prototype.stop = function() {
    window.clearInterval(this.poll_interval);
};

MirrorDom.Broadcaster.prototype.check_node = function(diffs, istack, node) {
    if (node.tagName == "SELECT") {
        diffs.push(['attribs', istack.slice(), { 
            "selectedIndex": node.selectedIndex
        }]);
    } else if (node.tagName == "INPUT") {
        diffs.push(['attribs', istack.slice(), { 
            "value": node.value
        }]);
    }
};

MirrorDom.Broadcaster.prototype.get_nodes_with_properties = function(dom_root) {
    // generate a list of diffs from nodes that have properties that
    // won't be represented in innerHTML
    var node = dom_root;
    var istack = [];
    var diffs = [];

    if (!node.firstChild) {
        return [];
    }

    while (true) {
        if (node.firstChild) {
            node = node.firstChild;
            istack.push(0);
            this.check_node(diffs, istack, node);
        } else if (node.nextSibling) {  
            node = node.nextSibling;
            istack[istack.length-1]++;
            this.check_node(diffs, istack, node);
        } else {
            while (!node.nextSibling) {
                node = node.parentNode;
                if (node === dom_root) {
                    return diffs;
                }
                istack.pop();
                this.check_node(diffs, istack, node);
            }
            node = node.nextSibling;
            istack[istack.length-1]++;
            this.check_node(diffs, istack, node);
        }
    }
    // unreachable
    return null;
};

MirrorDom.Broadcaster.prototype.node_at_path = function(root, ipath) {
    var node = root;
    for (var i=0; i < ipath.length; i++) {
        node = MirrorDom.Util.apply_ignore_nodes(node.firstChild);
        for (var j=0; j < ipath[i]; j++) {
            node = MirrorDom.Util.apply_ignore_nodes(node.nextSibling);
        }
    }
    return node;
};

/**
 * @param poll_interval     Interval between scans (ms)
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
MirrorDom.Broadcaster.prototype.init = function(options) {
    if (options.pusher) {
        this.pusher = options.pusher;
    } else {
        this.pusher = new MirrorDom.JQueryXHRPusher(options.root_url);
    }

    this.poll_interval = options.poll_interval != null ? options.poll_interval : 1000;

    if (options.iframe) {
        this.iframe = options.iframe;
    }
};

/* JQuery-XHR implementation of server push - we just POST all the data to
 * root_url + the method name */
 
MirrorDom.JQueryXHRPusher = function(root_url) {
    this.root_url = root_url;
};

MirrorDom.JQueryXHRPusher.prototype.push = function(method, args, callback) {
    for (var k in args) {
        if (jQuery.isPlainObject(args[k]) || jQuery.isArray(args[k])) {
            args[k] = JSON.stringify(args[k]);
        }
    }
    jQuery.post(this.root_url + method, args, function(result) {
        //callback(JSON.parse(result));
        if (callback) callback(result);
    });
};
