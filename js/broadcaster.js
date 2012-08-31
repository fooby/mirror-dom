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

// Class attributes...?
MirrorDom.Broadcaster.PROP_NAMES = ["value", "checked"];

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

MirrorDom.Broadcaster.prototype.clone_node = function(node) {
    // deep copy.
    var clone = {};
    clone.nodeName = node.nodeName;
    clone.attributes = {};
    clone.nodeType = node.nodeType;
    if (node.attributes) {
        for (var i=0; i < node.attributes.length; i++) {
            var attrib = node.attributes[i];

            // IE thing
            if (attrib.specified) {
                clone.attributes[attrib.name] = attrib.value;
            }
        }
    }

    // include properties that aren't reflected as DOM attributes
    var prop_names = MirrorDom.Broadcaster.PROP_NAMES;
    for (i=0; i < prop_names.length; i++) {
        var name = prop_names[i];
        if (name in node) {
            clone.attributes[name] = node[name];
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
                this.get_nodes_with_properties(node)]);
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
 * Returns true if different, false if same
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

    var diff_attribs = {};
    var dattribs = {};

    var cattribs = cnode.attributes;
    var diff = false;
    var key;
    var attrib;

    //debugger;

    if (dnode.attributes) {
        // convert .attributes map to an object dict
        for (var i=0; i < dnode.attributes.length; i++) {
            // IE hack for "specified" attributes (otherwise it returns EVARYTING)
            if (dnode.attributes[i].specified) {
                dattribs[dnode.attributes[i].name] = dnode.attributes[i].nodeValue;  
            }
        }

        // include properties that aren't reflected as DOM attributes
        for (i=0; i < MirrorDom.Broadcaster.PROP_NAMES.length; i++) {
            var name = MirrorDom.Broadcaster.PROP_NAMES[i];
            if (name in dnode) {
                dattribs[name] = dnode[name];
            }
        }

        // any attribs been added/changed?
        for (key in dattribs) {
            attrib = dattribs[key];
            //if (cattribs[key] != attrib) {

            // Derek EXPERIMENTAL HACK: For some reason the attributes may have been stringified
            //if (cattribs[key] != attrib && String(cattribs[key]) != String(attrib)) {
            if (cattribs[key] != attrib) {
                diff_attribs[key] = attrib;
                diff = true;
            }
        }
    }

    // any attribs been removed?
    for (key in cattribs) {
        if (!cattribs[key].specified) {
            continue;
        }

        if (dattribs) {
            attrib = dattribs[key];
        }
        // if (!dattribs || (attrib != cattribs[key] && String(attrib) != String(cattribs[key]))) {

        if (!dattribs || (attrib != cattribs[key])) {
            if (attrib) {
                diff_attribs[key] = attrib;
            } else {
                diff_attribs[key] = null;
            }
            diff = true;
        }
    }


    if (diff) {
        diffs.push(['attribs', ipath.slice(), diff_attribs]);
        return false;
    }

    return false;
};

MirrorDom.Broadcaster.prototype.diff_dom2 = function(dom_root, cloned_root) {
    var startTime = new Date().getTime();
    var node = dom_root;
    var cnode = cloned_root;

    // Basically a glorified "current position" indicator
    var istack = [];
    var diffs = [];

    // Alright, before we start:
    //
    // I'm going to introduce the terminology "actual" and "cloned" in the
    // following comments.
    //
    // Actual: The current DOM being viewed in the browser
    // Cloned: A representation of the previous state of the DOM at
    //         the time we did our last diff.

    // Step 1 when visiting a node is to compare the node's tagNames and
    // attributes. Step 2 is to iterate through the node's children, and Step 3
    // is to traverse onto the next sibling - or, if no more siblings, then up
    // to the parent.

    // This variable is set to false when first visiting a node, and true
    // when exiting (i.e. ready to traverse).
    var finished_comparing_node = false;
    var ascend_parent = false;

    // Keep tabs on the parents
    var node_parent = null;
    var cnode_parent = null;
   
    while (true) {
        // node is the actual node we're focusing on
        // cnode is the corresponding node from the cloned tree

        // Either:
        // 1) Cloned node does not exist, indicating recently added nodes
        // 2) Actual node does not exist, indicating recently removed nodes
        // 3) Both exist, so we're going to have to compare them and
        //    traverse children
        //
        // Special case: Both actual and cloned nodes are null, indicating
        // we've reached the end of traversing siblings

        // We've reached the end of traversing siblings, go back to parent
        if (node == null && cnode == null) {
        } else if (cnode == null) {
            // Scenario 1: Cloned node does not exist
            // 
            // One or more nodes have been added
            while (node) {
                istack[istack.length-1]++;
                this.add_node_diff(diffs, istack, node);
                node = node.nextSibling;
            }

            // At this point, both cnode and node should be null
            ascend_parent = true;
            finished_comparing_node = true;
        } else if (node == null) {
            // Scenario 2: Actual node does not exist
            //
            // One or more nodes have been removed
            diffs.push(['deleted', istack.slice()]);

            // Set cnode to null, in order to trigger behaviour to go back up
            // the parent
            ascend_parent = true;
            finished_comparing_node = true;
        }

        
        // Scenario 3: Begin comparing the node
        // We are going to:
        // 1) Compare the node tagNames, attributes, properties
        // 2) Traverse and compare the nodes' children
        if (!finished_comparing_node) {

            // Let's start by comparing the two nodes
            var changed = this.compare_nodes(diffs, istack, node,
                    cnode);

            if (!changed) {
                // Nodes are the same, descend into children

                if (node.firstChild == null && cnode.firstChild == null) {
                    // Ok, nodes are the same, no children on either
                    // node...proceed to next sibling!
                    finished_comparing_node = true;
                }
                else {
                    node_parent = node;
                    cnode_parent = cnode;
                    node = node.firstChild;
                    cnode = cnode.firstChild;
                    
                    istack.push(0);
                    continue
                }
            }
            else {
                // compare_nodes has already added a node diff, so
                // no further action needed
                finished_comparing_node = true;
            }
        }

        // Finished comparing the node, perform traversal onto next sibling or parent
        if (finished_comparing_node) {
            if (!ascend_parent) {
                // We have compared the children (or no children were present),
                // let's traverse to the next sibling. If no siblings then
                // ascend to parent. 
                node = node.nextSibling;
                cnode = cnode.nextSibling;

                if (node == null && cnode == null) {

                    // Test if we're back at the root element.
                    // Semi hack: The parent of an actual HTML node is the Document node,
                    // while the parent of the cloned HTML node is None.
                    // So...yeah, we expect ONLY the cnode's parent to be null
                    // at the root node.
                    if (node_parent == null || cnode_parent == null) {
                        // We're back at the root element, so we've finished!
                        break;
                    }

                    ascend_parent = true;
                }
            }

            if (ascend_parent) {
                // Ok, go back up the parent
                node = node_parent;
                cnode = cnode_parent;
                node_parent = node.parentNode;
                cnode_parent = cnode.parentNode;

                istack.pop();

                // This means we've finished comparing the parent node
                finished_comparing_node = true;
                ascend_parent = false;
            }
            else {
                // Move onto the next sibling
                istack[istack.length-1]++;
                finished_comparing_node = false
            }
        }
    }
    return diffs;
}

MirrorDom.Broadcaster.prototype.diff_dom = function(dom_root, cloned_root) {
    var startTime = new Date().getTime();
    var node = dom_root;
    var cnode = cloned_root;
    var istack = [];
    var diffs = [];


    while (true) {

        // Alright, before we start:
        //
        // node is the current node we're focusing on
        // cnode is the corresponding node from the cloned tree
        //
        // I'm going to introduce the terminology "actual" and "cloned" in the
        // following comments.
        //
        // actual: The current DOM being viewed in the browser
        // cloned: A representation of the previous state of the DOM at
        //         the time we did our last diff.
        //
        // The strategy is to compare the actual and cloned trees to detect
        // changes in the DOM since our last diff. At the end we'll update the
        // cloned tree to prepare for the next diff.
        // 
        // We perform a lockstep tree traversal using the following order of
        // traversal:
        //
        // 1) Down into the node's children
        // 2) Across the node's siblings
        // 3) Ascend into the node's uncles (I'll call this uncle ascent)
        //
        // So we're performing a depth first tree traversal. But it might look
        // a bit weird though, as we're using firstChild, nextSibling and
        // parentNode to traverse instead of more traditional stack based
        // techniques.
        
           
        // Traversal part 1: Child descent
        // --------------------------------------------------------------------
        //
        // Node has a child, let's compare the children of this node and
        // the cloned node. Possible scenarios are:
        //
        // 1) Actual node has a child, but cloned node does not: A new child
        //   was recently added to the node
        //
        // 2) Actual node child and cloned node child are identical (does
        //    not include children): We descend into child
        //
        // 3) Actual node child and cloned node child are different:
        //    TODO: Explainme
        //
        // 4) Actual node has no child, but the cloned node does: Actual node
        //    has had its child deleted, add diff entry to remove all
        //    corresponding children
        //
        if (node.firstChild) {

            if (!this.compare_nodes(diffs, istack.concat(0), 
                    node.firstChild, cnode.firstChild)) {

                // Child descent 2: Nodes identical, descend into children
                istack.push(0);
                node = node.firstChild;
                cnode = cnode.firstChild;
                continue;
            }

            // Child descent 3: We proceed to comparing siblings. 
            // (Nodes are too different .. dont descend, drop to next clause)

        } else if (cnode.firstChild) {
            // Child descent 4: Node's child recently deleted (don't forget to
            // check possible bug)
            diffs.push(['deleted', istack.concat(0)]);
        }

        // Traversal part 2: Sibling traversal
        // --------------------------------------------------------------------
        // If we're here, that means we're about to go compare sibling nodes
        // (i.e. the node to the immediate right of our current node)
        //
        // Here are the scenarios for that:
        // 1) Siblings are different: Right now, we're going to be lazy and
        //    iterate through all remaining siblings in order to perform a
        //    wholesale replacement of ALL remaining siblings
        //    Immediately proceed into traversal part 3 (uncle ascent)
        //
        //    Possible bug: If cloned node has more siblings than actual node, then
        //                  applying the diff will leave extra siblings
        //
        // 1a) Actual node has sibling, but cloned node does not:
        //    This indicates that sibling nodes were recently added.
        //
        //    Same codepath as 1, just iterate through all remaining actual
        //    siblings and insert each one into diffs log.
        //
        //
        // 2) Siblings are the same: Iterate into the sibling node (i.e. child
        //    descent on that node and then sibling iteration)
        //
        // 3) Actual node has no sibling:
        //    
        //    We've reached the end of the siblings. It's possible that the
        //    cloned node has further remaining siblings, indicating that the
        //    actual node has had siblings recently removed.
        //
        //    a) Indicate deletion of any remaining cloned node siblings and
        //       proceed into uncle ascent.

        if (node.nextSibling) {
            istack[istack.length-1]++;
            if (this.compare_nodes(diffs, istack,
                    node.nextSibling, cnode.nextSibling)) {

                // Sibling traversal 1: Siblings are different OR
                // Sibling traversal 1a: Actual node sibling has been recently added

                // found different sibling; iterate through remainder 
                // of siblings without checking the cloned tree (too hard)
                // and add each to the diff list without descending
                node = node.nextSibling;

                while (node.nextSibling) {
                    istack[istack.length-1]++;
                    this.add_node_diff(diffs, istack, node.nextSibling);
                    node = node.nextSibling;
                }
                // (drop through to next clause)

            } else {
                // Sibling traversal 2: Siblings match , proceed
                node = node.nextSibling;
                cnode = cnode.nextSibling;
                continue;
            }
        }

        // Sibling traversal 3 (well, sibling traversal 1 and 1a go through
        // here too but this comment doesn't apply to those):
        // 
        // We've reached the end of the actual node's siblings, we need to
        // ascend to the tree's uncle

        // Traversal part 3: Uncle ascent
        // --------------------------------------------------------------------
        //
        // We need to 

        // tree ascent
        while (true) {
            // implicitly - !node.nextSibling && 
            // (!node.firstChild || we are skipping the descent) , ascend
            while (!node.nextSibling) {
                if (node == dom_root) {
                    return diffs;
                }

                if (cnode.nextSibling) {
                    // cloned tree has a nextSibling, but its removed from the DOM
                    diffs.push(['deleted', 
                        istack.slice(0, istack.length-1).concat(
                            istack[istack.length-1]+1)]);
                }

                istack.pop();
                node = node.parentNode;
                cnode = cnode.parentNode;
            }

            istack[istack.length-1]++;
            if (this.compare_nodes(diffs, istack, node.nextSibling, 
                        cnode.nextSibling)) 
            {
                // found different sibling; 
                // iterate through remainder of siblings
                node = node.nextSibling;
                if (cnode.nextSibling) {
                    cnode = cnode.nextSibling;
                }

                while (node.nextSibling) {
                    istack[istack.length-1]++;
                    this.add_node_diff(diffs, istack, node.nextSibling);
                    node = node.nextSibling;
                    if (cnode.nextSibling) {
                        cnode = cnode.nextSibling;
                    }
                }

                if (cnode.nextSibling) {
                    // cloned tree has a nextSibling, but its removed from the DOM
                    diffs.push(['deleted', 
                        istack.slice(0, istack.length-1).concat(
                            istack[istack.length-1]+1)]);
                }

                // resume ascent
                continue;
            } else {
                node = node.nextSibling;
                cnode = cnode.nextSibling;
                break;
            }
        }
    }

    // unreachable?
    return diffs;
};

/**
 * Returns a copy of a DOM tree
 */
MirrorDom.Broadcaster.prototype.clone_dom = function(root) {
    var startTime = new Date().getTime();
    var node = root;
    var cloned_node = this.clone_node(root);
    var cloned_root = cloned_node;
    while (true) {
        if (node.firstChild) {
            node = node.firstChild;
            cloned_node.firstChild = this.clone_node(node);
            cloned_node.firstChild.parentNode = cloned_node;
            cloned_node = cloned_node.firstChild;
        } else if (node.nextSibling) {
            node = node.nextSibling;
            cloned_node.nextSibling = this.clone_node(node);
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
            cloned_node.nextSibling = this.clone_node(node);
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
    } else if (this.new_page_loaded) {
        this.new_page_loaded = false;
        this.send_new_page_loaded();
    } else {
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
