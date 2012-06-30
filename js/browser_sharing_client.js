var MirrorDom = { Client: {} };

MirrorDom.Client.PROP_NAMES = ["value", "checked"];

MirrorDom.Client.clone_node = function(node) {
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
    for (i=0; i < MirrorDom.Client.PROP_NAMES.length; i++) {
        var name = MirrorDom.Client.PROP_NAMES[i];
        if (name in node) {
            clone.attributes[name] = node[name];
        }
    }
    clone.nodeValue = node.nodeValue;

    return clone;
};

MirrorDom.Client.add_node_diff = function(diffs, ipath, node) {
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

MirrorDom.Client.compare_nodes = function(diffs, ipath, dnode, cnode) {
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
        for (i=0; i < MirrorDom.Client.PROP_NAMES.length; i++) {
            var name = MirrorDom.Client.PROP_NAMES[i];
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

MirrorDom.Client.diff_dom = function(dom_root, cloned_root) {
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

MirrorDom.Client.clone_dom = function(root) {
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

MirrorDom.Client.get_html = function() {
    MirrorDom.Client.cloned_dom = 
        MirrorDom.Client.clone_dom(document.documentElement);
    var html_node = document.documentElement;
    
    // for first snapshot, just send html
    return html_node.innerHTML;
};

MirrorDom.Client.get_diff = function() {
    var diff = this.diff_dom(document.documentElement, this.cloned_dom);
    
    if (diff.length) {
        // update the cloned dom as we detected changes.
        // todo: update cloned dom using diff!
        this.cloned_dom = this.clone_dom(document.documentElement);
    }

    return diff;
};

MirrorDom.Client.new_window = function() {
    MirrorDom.Client.pusher.push("new_window", {
            "html": MirrorDom.Client.get_html()
    },
    function(window_id) {
        // window.name persists across page loads
        window.name = window_id;
        window.sending = false;
    });
};

MirrorDom.Client.start = function() {
    window.browser_sharing_interval = window.setInterval(function() {
        if (window.sending) {
            return;
        }

        if (!MirrorDom.Client.cloned_dom) {
            // first call after page load
            window.sending = true;
            if (window.name) {
                // already has a window id
                MirrorDom.Client.pusher.push("reset", {
                    "window_id": window.name, 
                    "html": MirrorDom.Client.get_html()
                },
                function(response) {
                    window.sending = false;
                    if (response === null) {
                        // server doesn't know about our id? start a new
                        // session
                        MirrorDom.Client.new_window()
                    }
                });
            } else {
                MirrorDom.Client.new_window()
            }
        } else {
            // send difference between now and the cloned dom
            var diff = MirrorDom.Client.get_diff();
            if (diff.length) {
                window.sending = true;
                MirrorDom.Client.pusher.push("add_diff", {
                    "window_id": window.name,
                    "diff": diff
                }, 
                function() {
                    window.sending = false;
                });
            }
        }
    }, 1000);
};

MirrorDom.Client.stop = function() {
    window.clearInterval(window.browser_sharing_interval);
};

MirrorDom.Client.check_node = function(diffs, istack, node) {
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

MirrorDom.Client.get_nodes_with_properties = function(dom_root) {
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

MirrorDom.Client.init = function(options) {
    if (options.pusher) {
        this.pusher = pusher;
    } else {
        this.pusher = new MirrorDom.Client.JQueryXHRPusher(options.root_url);
    }
};

/* JQuery-XHR implementation of server push - we just POST all the data to
 * root_url + the method name */
 
MirrorDom.Client.JQueryXHRPusher = function(root_url) {
    this.root_url = root_url;
};

MirrorDom.Client.JQueryXHRPusher.prototype.push = function(method, args, callback) {
    if (method == "add_diff") {
        args.diff = JSON.stringify(args.diff);
    }
    jQuery.post(this.root_url + method, args, callback);
};
