var MirrorDom = { Broadcaster: {} };

MirrorDom.Broadcaster = function(options) {
    this.cloned_dom = null;
    this.interval_event = null;
    this.init(options);
}

// Class attributes...?
MirrorDom.Broadcaster.PROP_NAMES = ["value", "checked"];

MirrorDom.Broadcaster.prototype.clone_node = function(node) {
    // deep copy.
    var clone = {};
    clone.nodeName = node.nodeName;
    clone.attributes = {};
    clone.nodeType = node.nodeType;
    if (node.attributes) {
        for (var i=0; i < node.attributes.length; i++) {
            var attrib = node.attributes[i];
            clone.attributes[attrib.name] = attrib.value;
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

MirrorDom.Broadcaster.prototype.compare_nodes = function(diffs, ipath, dnode, cnode) {
    if (!cnode) {
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

    if (dnode.attributes) {
        // convert .attributes map to an object dict
        for (var i=0; i < dnode.attributes.length; i++) {
            dattribs[dnode.attributes[i].name] = dnode.attributes[i].nodeValue;  
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
            if (cattribs[key] != attrib) {
                diff_attribs[key] = attrib;
                diff = true;
            }
        }
    }

    // any attribs been removed?
    for (key in cattribs) {
        if (dattribs) {
            attrib = dattribs[key];
        }
        if (!dattribs || attrib != cattribs[key]) {
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

MirrorDom.Broadcaster.prototype.diff_dom = function(dom_root, cloned_root) {
    var startTime = new Date().getTime();
    var node = dom_root;
    var cnode = cloned_root;
    var istack = [];
    var diffs = [];
    while (true) {
        if (node.firstChild) {
            if (!this.compare_nodes(diffs, istack.concat(0), 
                    node.firstChild, cnode.firstChild)) {
                istack.push(0);
                node = node.firstChild;
                cnode = cnode.firstChild;
                continue;
            }
            // else, nodes are too different .. dont descend, drop to next clause
        } else if (cnode.firstChild) {
            // cloned tree has a firstChild, but its removed from the DOM
            diffs.push(['deleted', istack.concat(0)]);
        }

        if (node.nextSibling) {
            istack[istack.length-1]++;
            if (this.compare_nodes(diffs, istack,
                    node.nextSibling, cnode.nextSibling)) {
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
                node = node.nextSibling;
                cnode = cnode.nextSibling;
                continue;
            }
        }

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

MirrorDom.Broadcaster.prototype.get_document = function() {
    var d = null;
    if (this.iframe) {
        // Retrieve iframe document
        if (this.iframe.contentDocument) {
            // Firefox
            d = this.iframe.contentDocument;
        }
        else if (this.iframe.contentWindow) {
            // IE
            d = this.iframe.contentWindow.contentDocument;
        }
        else {
            console.log("What the hell happened");
        }
    } else {
        d = document;
    }

    return d;
}

MirrorDom.Broadcaster.prototype.get_html = function() {
    var d = this.get_document();
    this.cloned_dom = this.clone_dom(d.documentElement);
    var html_node = d.documentElement;
    
    // for first snapshot, just send html
    return html_node.innerHTML;
};

MirrorDom.Broadcaster.prototype.get_diff = function() {
    var d = this.get_document();
    var diff = this.diff_dom(d.documentElement, this.cloned_dom);
    
    if (diff.length) {
        // update the cloned dom as we detected changes.
        // todo: update cloned dom using diff!
        this.cloned_dom = this.clone_dom(d.documentElement);
    }

    return diff;
};

MirrorDom.Broadcaster.prototype.new_window = function() {
    this.pusher.push("new_window", {
        "html": this.get_html()
    },
    function(window_id) {
        // window.name persists across page loads
        window.name = window_id;
        window.sending = false;
    });
};

MirrorDom.Broadcaster.prototype.poll = function() {
    if (window.sending) {
        return;
    }

    if (!this.cloned_dom) {
        // first call after page load
        window.sending = true;
        if (window.name) {
            // already has a window id
            this.pusher.push("reset", {
                "window_id": window.name, 
                "html": this.get_html()
            },
            function(response) {
                window.sending = false;
                if (response === null) {
                    // server doesn't know about our id? start a new
                    // session
                    this.new_window()
                }
            });
        } else {
            this.new_window()
        }
    } else {
        // send difference between now and the cloned dom
        var diff = this.get_diff();
        if (diff.length) {
            window.sending = true;
            this.pusher.push("add_diff", {
                "window_id": window.name,
                "diff": diff
            }, 
            function() {
                window.sending = false;
            });
        }
    }
}

MirrorDom.Broadcaster.prototype.start = function() {
    var self = this;
    console.log("Poll interval: " + this.poll_interval);
    this.interval_event = window.setInterval(function() {
        self.poll();
    }, this.poll_interval);
};

MirrorDom.Broadcaster.prototype.stop = function() {
    window.clearInterval(window.browser_sharing_interval);
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
        this.pusher = pusher;
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
        if ($.isPlainObject(args[k]) || $.isArray(args[k])) {
            args[k] = JSON.stringify(args[k]);
        }
    }
    jQuery.post(this.root_url + method, args, callback);
};
