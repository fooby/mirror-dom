XPLAN.namespace("browser_sharing.viewer");

XPLAN.browser_sharing.viewer.next_change_ids = {};

XPLAN.browser_sharing.node_at_path = function(root, ipath) {
    var node = root;
    for (var i=0; i < ipath.length; i++) {
        /*if (!node.firstChild) {
            debugger;
        }*/
        node = node.firstChild;
        for (var j=0; j < ipath[i]; j++) {
            /*if (!node.nextSibling) {
                debugger;
            }*/
            node = node.nextSibling;            
        }
    }
    return node;
};

XPLAN.browser_sharing.viewer.apply_attr = function(k, v, node, ipath) {
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

XPLAN.browser_sharing.viewer.apply_diffs = function(doc_elem, diffs) {
    for (var i=0; i < diffs.length; i++) {
        var diff = diffs[i];        
        console.log(diff[0] + "|" + diff[1] + "|");
        if (diff[0] == 'node' || diff[0] == 'text') {
            var parent = XPLAN.browser_sharing.node_at_path(doc_elem, 
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
            var node = XPLAN.browser_sharing.node_at_path(doc_elem, diff[1]);
            for (var k in diff[2]) {
                XPLAN.browser_sharing.viewer.apply_attr(k, diff[2][k], node,
                        diff[1]);
            }
        } else if (diff[0] == 'deleted') {
            var node = XPLAN.browser_sharing.node_at_path(doc_elem, 
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

XPLAN.browser_sharing.viewer.start = function(client_id, container_id) {
    window.browser_sharing_interval = window.setInterval(function() {
        if (window.receiving) {
            return;
        }
        window.receiving = true;
        XMLRPC.call("browser_sharing.get_update",
            [client_id, 
            XPLAN.browser_sharing.viewer.next_change_ids],
            function(result) 
        {
            var container = jQuery("#" + container_id);
            for (var window_id in result) {
                var name = "viewer_" + window_id;
                var viewer = container.find("[name]=" + name);
                if (!viewer.length) {
                    container.append(
                        "<iframe name='" + name + 
                        "' width='1024' height='900'></iframe>");
                    viewer = container.find(":last-child");
                }
                var change_log = result[window_id];

                if (change_log.init_html) {
                    var html = change_log.init_html;
                    html.replace("XPLAN.browser_sharing.client.start();", "");
                    html = '<html>' + html + '</html>';
                    viewer.get(0).contentDocument.documentElement.innerHTML = html;
                }
                if (change_log.diffs) {
                    XPLAN.browser_sharing.viewer.apply_diffs(
                        viewer.get(0).contentDocument.documentElement,
                        change_log.diffs);
                }

                XPLAN.browser_sharing.viewer.next_change_ids[window_id] =
                    change_log.last_change_id + 1;
            }
            window.receiving = false;
        });
    }, 1000);
};

