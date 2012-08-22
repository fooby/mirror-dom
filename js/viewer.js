var MirrorDom = { Viewer: {} };

MirrorDom.Viewer = function(options) {
    this.receiving = false;
    this.next_change_ids = {};
    this.init(options);
}

MirrorDom.Viewer.prototype.node_at_path = function(root, ipath) {
    console.log("node_at_path: " + ipath);
    var node = root;
    for (var i=0; i < ipath.length; i++) {
        node = node.firstChild;
        console.log("node_at_path: i: " + i + " node: " + node);
        for (var j=0; j < ipath[i]; j++) {
            /*if (!node.nextSibling) {
                debugger;
            }*/
            node = node.nextSibling;            
            console.log("node_at_path: j: " + j + " node: " + node);
        }
    }
    return node;
};

MirrorDom.Viewer.prototype.apply_attr = function(k, v, node, ipath) {
    // special cases
    if (k == "selected" && node.tagName == "OPTION") {
        // selected <option>. null would indicate
        // the select attribute as been deleted; any
        // other value means we need to call .selectedIndex
        // on the parent <select> to have the browser actually react
        if (v !== null) {
            if (node.parentNode.tagName == "SELECT") {                
                node.parentNode.selectedIndex = ipath[ipath.length-1];
            }
        }        
    } else if (k == "checked" && node.tagName == "INPUT") {
        // checked <input>.
        node.checked = (v !== null);
        return;
    } else if (k == "value") {
        node.value = v;
        return;
    }

    if (v === null) {
        console.log("removeAttribute " + k);
        node.removeAttribute(k);
    } else {
        console.log("setAttribute " + k + ": " + v);        
        node.setAttribute(k, v);
    }
};

MirrorDom.Viewer.prototype.apply_diffs = function(doc_elem, diffs) {
    for (var i=0; i < diffs.length; i++) {
        var diff = diffs[i];        
        console.log("apply_diff with type: " + diff[0] + " ipath: " + diff[1]);
        if (diff[0] == 'node' || diff[0] == 'text') {
            var parent = this.node_at_path(doc_elem, 
                diff[1].slice(0, diff[1].length-1));

            var node = parent.firstChild;

            // go to node referenced in offset and replace it 
            // if it exists; and delete all following nodes
            for (var d=0; d < diff[1][diff[1].length-1]; d++) {
                node = node.nextSibling;
            }

            if (node) {
                console.log('replacing: ' + node.tagName + ": " + 
                        node.innerHTML);
            } else {
                console.log('not replacing, null node');
            }

            while (node) {
                var next_node = node.nextSibling;
                parent.removeChild(node);
                node = next_node;
            }

            // create new element from the cloned node
            if (diff[0] == 'node') {
                var cloned_node = diff[3];
                var new_elem = document.createElement(
                        cloned_node.nodeName);

                for (var k in cloned_node.attributes) {
                    new_elem.setAttribute(k, cloned_node.attributes[k]);
                }

                new_elem.innerHTML = diff[2];

                // apply diffs of properties like .value, selectedIndex
                // etc which wouldn't be in innerHTML
                this.apply_diffs(new_elem, diff[4]);
            } else {
                var new_elem = document.createTextNode(diff[2]);
            }
            parent.appendChild(new_elem);

        } else if (diff[0] == 'attribs') {
            var node = this.node_at_path(doc_elem, diff[1]);
            for (var k in diff[2]) {
                this.apply_attr(k, diff[2][k], node,
                        diff[1]);
            }
        } else if (diff[0] == 'deleted') {
            var node = this.node_at_path(doc_elem, 
                    diff[1]);
            // remove remaining siblings and node itself
            while (node) {
                console.log('deleted: ' + node.tagName + ": " + node.innerHTML + 
                        " parent: " + node.parentNode.innerHTML);

                var next_node = node.nextSibling;
                node.parentNode.removeChild(node);
                node = next_node;
            }
        } 
    }
}

MirrorDom.Viewer.prototype.get_output_document = function() {
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
    }

    return d;
}

MirrorDom.Viewer.prototype.poll = function() {
    console.log("Polling!");
    if (this.receiving) {
        console.log("Already receiving, aborting");
        return;
    }


    this.receiving = true;
    var self = this;
    this.puller.pull("get_update", {
            "change_ids": this.next_change_ids
        }, 
        function(result) {
            self.receive_updates(result);
            self.receiving = false;
        }
    );
}

MirrorDom.Viewer.prototype.receive_updates = function(result) {
    for (var window_id in result) {
        var output_document = this.get_output_document();
        var change_log = result[window_id];

        if (change_log.init_html) {
            var html = change_log.init_html;
            html = ['<html>', html, '</html>'].join("");
            // note that viewer won't execute scripts from the client
            // because we use innerHTML to insert (although the
            // <script> elements will still be in the DOM)
            output_document.documentElement.innerHTML = html;
            console.log(html);
        }

        if (change_log.diffs) {
            this.apply_diffs(
                output_document.documentElement,
                change_log.diffs);
        }

        this.next_change_ids[window_id] =
            change_log.last_change_id + 1;
    }
}

MirrorDom.Viewer.prototype.start = function(container_id) {
    var self = this;
    this.interval_event = window.setInterval(function() {
        self.poll();
    }, this.poll_interval);
};

MirrorDom.Viewer.prototype.init = function(options) {
    if (options.puller) {
        this.puller = puller;
    } else {
        this.puller = new MirrorDom.Viewer.JQueryXHRPuller(options.root_url);
    }

    this.iframe = options.iframe;
    this.poll_interval = options.poll_interval != null ? options.poll_interval : 1000;
};

MirrorDom.Viewer.JQueryXHRPuller = function(root_url) {
    this.root_url = root_url;
};

MirrorDom.Viewer.JQueryXHRPuller.prototype.pull = function(method, args, callback) {
    if (method == "get_update") {
        args.change_ids = JSON.stringify(args.change_ids);
    }
    jQuery.get(this.root_url + method, args, callback);
};
