/**
 * MirrorDom viewer proof of concept
 */

var MirrorDom = MirrorDom === undefined ? {} : MirrorDom;

MirrorDom.Viewer = function(options) {
    this.receiving = false;
    this.iframe = null;
    this.next_change_ids = {};
    this.init(options);
}

MirrorDom.Viewer.prototype.get_document_object = function() {
    return MirrorDom.Util.get_document_object_from_iframe(this.iframe);
}

MirrorDom.Viewer.prototype.get_document_element = function() {
    return this.get_document_object().documentElement;
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
    if (window.ActiveXObject){
        s = xml_node.xml;
    }
    // code for Mozilla, Firefox, Opera, etc.
    else{
        s = (new XMLSerializer()).serializeToString(xml_node);
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
 */
MirrorDom.Viewer.prototype.apply_document = function(data) {

    //var full_html = ['<html>', html, '</html>'].join("");
    // note that viewer won't execute scripts from the client
    // because we use innerHTML to insert (although the
    // <script> elements will still be in the DOM)
    //doc_elem.innerHTML = full_html;
    //console.log(full_html);
    //jQuery(doc_elem).html(full_html);
    //console.log(full_html);
    
    var doc_elem = this.get_document_element();

    var new_doc = jQuery(jQuery.parseXML(data));
    var new_head_node = new_doc.find("head");

    if (new_head_node.length > 0) {
        var current_head = doc_elem.getElementsByTagName('head')[0];
        current_head = jQuery(current_head);
        this.copy_to_node(new_head_node, current_head, false);
    }

    var current_body = doc_elem.getElementsByTagName('body')[0];
    current_body = jQuery(current_body).empty();
    var new_body_node = new_doc.find("body");
    this.copy_to_node(new_body_node, current_body, true);

    /*var body = doc_elem.getElementsByTagName('body')[0];

    var head_html = data[0];
    var body_html = data[1];
    body.innerHTML = body_html;

    this.apply_head_html(doc_elem, head_html);*/
}

MirrorDom.Viewer.prototype.apply_diffs = function(diffs) {
    var doc_elem = this.get_document_element();

    for (var i=0; i < diffs.length; i++) {
        var diff = diffs[i];        


        // Diff structure:
        //
        // 0) "node" or "text"
        // 1) Path to node (node offsets at each level of tree)
        // 2) Inner HTML
        // 3) Element definition:
        //    - attributes: HTML attributes
        //    - nodeName:   Node name
        //    - nodeType:   Node type
        // 4) Extra properties to apply

        
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

                //new_elem.innerHTML = diff[2];
                // Derek HACK
                jQuery(new_elem).html(diff[2]);

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

MirrorDom.Viewer.prototype.poll = function() {
    if (this.receiving) {
        console.log("Already receiving, aborting");
        return;
    }

    console.log("POOL!");

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
        var doc_elem = this.get_document_element();
        var change_log = result[window_id];

        //debugger;
        if (change_log.init_html) {
            this.apply_document(change_log.init_html);
        }

        if (change_log.diffs) {
            this.apply_diffs(change_log.diffs);
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
        this.puller = options.puller;
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
