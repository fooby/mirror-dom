var MirrorDom = MirrorDom === undefined ? {} : MirrorDom;

//MirrorDom.Base.prototype.get_document_element = function() {
//    var d = this.get_document_object();
//    var doc_elem = d.documentElement;
//    return doc_elem;
//}

MirrorDom.Util = {}

/**
 * @param iframe        Iframe object
 */
MirrorDom.Util.get_document_object_from_iframe = function(iframe) {
    var d = null;
    if (iframe) {
        // Retrieve iframe document
        if (iframe.contentDocument) {
            // Firefox
            d = iframe.contentDocument;
        }
        else if (iframe.contentWindow) {
            // IE
            d = iframe.contentWindow.document;
        }
        else {
            console.log("What the hell happened");
        }
    }
    else {
        throw new Error("iframe has not been set");
    }

    return d;
}

/**
 * Checks whether we should ignore the node when building the tree
 */
MirrorDom.Util.should_ignore_node = function(node) {
    if (node == undefined) {
        debugger;
    }

    switch (node.nodeType) {
        case 3: // case Node.TEXT_NODE:
            // Ignore if text node is only whitespace
            var has_content = /\S/.test(node.nodeValue);
            return !has_content;

                    
        case 1: //case Node.ELEMENT_NODE:
            // Ignore certain element tags 
            switch (node.nodeName) {
                case "META":
                case "SCRIPT":
                    return true;
                default:
                    return false;
            }
            break;
    }

    // Ignore everything else
    return true;
}

/**
 * Given a DOM node, determine if we should ignore it
 */
MirrorDom.Util.apply_ignore_nodes = function(node) {
    while (node != null && MirrorDom.Util.should_ignore_node(node)) {
        node = node.nextSibling;
    }

    return node;
}

//MirrorDom.Util.only_elements_and_apply_ignore_nodes = function(node) {
//    while (node != null &&
//           node.nodeType != 1 &&
//           MirrorDom.Util.should_ignore_node(node)) {
//        node = node.nextSibling;
//    }
//
//    return node;
//}

/**
 * Set property on a DOM node.
 *
 * @param node              DOM node or arbitrary object (for "cloned" nodes)
 *
 * @param prop_lookup       An object attribute path
 *                          e.g. ["style", "cssText"]
 *
 * @param force             Force create arbitrary objects to ensure the path
 *                          gets set (don't use on actual DOM nodes)
 */
MirrorDom.Util.set_property = function(node, prop_lookup, value, force) {
    var i;
    var prop = node;
    for (i = 0; i < prop_lookup.length - 1; i++) {
        if (!(prop_lookup[i] in prop)) {
            if (force) {
                prop[prop_lookup[i]] = {};
            } else {
                // Nope
                return;
            }
        }
        prop = prop[prop_lookup[i]];
    }
    prop[prop_lookup[i]] = value;
}

/**
 * Retrieve property from a DOM node.
 *
 * @param node              DOM node or arbitrary object (for "cloned" nodes)
 *
 * @param prop_lookup       An object attribute path
 *                          e.g. ["style", "cssText"]
 *                          
 */
MirrorDom.Util.get_property = function(node, prop_lookup) {
    var prop = node;
    for (var i = 0; i < prop_lookup.length; i++) {
        if (prop_lookup[i] in prop) {
            prop = prop[prop_lookup[i]];
        } else {
            return [false, null];
        }
    }
    return [true, prop];
}


/**
 * Retrieve list of properties from DOM node
 */
MirrorDom.Util.get_all_properties = function(node, prop_lookup_lost) {
}

/**
 * Split property path by "." (purely for style.cssText's benefit)
 *
 * Returns a list of [(original path, [list of path elements])]
 *
 * e.g. The if prop_paths is ["style.cssText"], the return value is
 *      [["style.cssText", ["style", "cssText"]]]
 */
MirrorDom.Util.process_property_paths = function(prop_paths) {
    var prop_names = [];
    for (var i = 0; i < prop_paths.length; i++) {
        var prop_text = prop_paths[i];
        prop_names.push([prop_text, prop_text.split('.')]);
    }
    return prop_names;
}

MirrorDom.Util.describe_node = function(node) {
    var desc = [];
    desc.push("<", node.nodeName);
    if (node.id) { desc.push(" #", node.id); }
    desc.push(">");
    return desc.join("")
}

MirrorDom.Util.describe_node_at_path = function(root, ipath) {
    var node = root;
    var path_desc = [];
    var terminate = false;

    for (var i = 0; i < ipath.length; i++) {
        var item_desc = [];
        var line_desc = [];

        node = MirrorDom.Util.apply_ignore_nodes(node.firstChild);
        for (var j=0; j <= ipath[i]; j++) {
            if (j != 0) {
                node = MirrorDom.Util.apply_ignore_nodes(node.nextSibling);
            }
            if (node == null) {
                item_desc = [j, ": ", "null :("];
                line_desc.push(item_desc.join(""));
                terminate = true;
                break;
            } else {
                item_desc = [j, ": ", MirrorDom.Util.describe_node(node)];
                line_desc.push(item_desc.join(""));
            }
        }

        path_desc.push(line_desc.join(" -> "));

        if (terminate) {
            break;
        }
    }
    return path_desc.join("\n");
}
