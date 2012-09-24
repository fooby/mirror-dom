var MirrorDom = MirrorDom === undefined ? {} : MirrorDom;

MirrorDom.Util = {}


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

MirrorDom.Util.PROPERTY_NAMES = ["disabled", "value", "checked", "style.cssText", "className", "colSpan"];
MirrorDom.Util.IGNORE_ATTRIBS = {"style": null};
MirrorDom.Util.PROPERTY_LOOKUP = MirrorDom.Util.process_property_paths(MirrorDom.Util.PROPERTY_NAMES);

/**
 * @param node      
 */
MirrorDom.Util.get_property_lookup_list = function(node) {
    if (node.namespaceURI == "http://www.w3.org/2000/svg") {
        return [];
    } else {
        return MirrorDom.Util.PROPERTY_LOOKUP;
    }
}

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
 * Given a DOM node, find the first sibling that we DON'T ignore.
 *
 * Ignores consecutive text nodes until the last one in the sequence.
 * (Text node content needs to be retrieved IN REVERSE)
 */
MirrorDom.Util.apply_ignore_nodes = function(node) {
    var possible_next_node = null;

    while (true) {
        if (node == null) {
            break;
        }

        // We need to peek ahead at the next node in order to perform
        // consecutive text node elimination.
        possible_next_node = node.nextSibling;
        while (possible_next_node != null &&
               MirrorDom.Util.should_ignore_node(possible_next_node)) {
            possible_next_node = possible_next_node.nextSibling;
        }

        var found = true;

        // Apply text node elimination. We'll accept text nodes as long as their
        // immediate next possible sibling isn't also a text node
        if (MirrorDom.Util.should_ignore_node(node)) {
            found = false;
        } else if (possible_next_node != null &&
                node.nodeType == 3 &&
                possible_next_node.nodeType == 3) {
            //console.log("Skipping consecutive text node")
            found = false;
        }

        if (found) {
            break;
        }

        node = possible_next_node;
    }

    return node;
}

/**
 * Assumes we're at the LAST text node in a chain of consecutive text nodes.
 * Constructs string by going backwards.
 */
MirrorDom.Util.get_text_node_content = function(node) {
    var value = [];
    while (node != null && node.nodeType == 3) {
        if (!MirrorDom.Util.should_ignore_node(node)) {
            value.unshift(node.nodeValue);
        }
        node = node.previousSibling;
    }
    return value.join("");
}

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
 * ============================================================================
 * Errors
 * ============================================================================
 */
MirrorDom.Util.PathError = function(root, path) {
    this.name = "PathError";
    this.root = root;
    this.path = path;
    this.message = "Couldn't retrieve path " + path.join(",") +
        " for node " + MirrorDom.Util.describe_node(root);
}
//MirrorDom.Util.PathError.prototype = new Error();
//MirrorDom.Util.PathError.prototype.constructor = MirrorDom.Util.PathError;

MirrorDom.Util.PathError.prototype.describe_path = function() {
    return MirrorDom.Util.describe_node_at_path(this.root, this.path);
}

MirrorDom.Util.DiffError = function(diff, root, path) {
    this.name = "PathError";
    this.diff = diff;
    this.root = root;
    this.path = path;
    this.message = "Couldn't apply diff [" + diff.join(",") +
        "] for node " + MirrorDom.Util.describe_node(root) + ", path " +
        path.join(",");
}

MirrorDom.Util.DiffError.prototype.describe_path = function() {
    return MirrorDom.Util.describe_node_at_path(this.root, this.path);
}

/**
 * ============================================================================
 * Path Utilities
 * ============================================================================
 */
MirrorDom.Util.get_properties = function(node) {
    if (node.nodeType == 1) {
        // Let's go check the node
        var new_props = {}
        var diff = false;
        for (var i = 0; i < this.PROPERTY_LOOKUP.length; i++) {
            var prop_text = this.PROPERTY_LOOKUP[i][0];
            var prop_lookup = this.PROPERTY_LOOKUP[i][1];
            var prop_result = MirrorDom.Util.get_property(node, prop_lookup);
            var prop_found = prop_result[0];
            var prop_value = prop_result[1];
            if (prop_found && (prop_value != "" && prop_value != null)) {
                new_props[prop_text] = prop_value;
                diff = true;
            }
        }
        if (diff) {
            return new_props;
        }
    }
    return null;
}


MirrorDom.Util.path_equal = function(x, y) {
    if (x.length != y.length) { return false; }
    for (var i = 0; i < x.length; i++) {
        if (x[i] != y[i]) { return false; }
    }
    return true;
}

/**
 * Returns true if "inside" is equal to or a child of "outside"
 *
 * e.g. [1,2,4,5,6], [1,2,4] = true
 *
 * Note that "outside" should be the SHORTER path (shorter means higher up)
 */
MirrorDom.Util.is_inside_path = function(inside, outside) {
    if (inside.length < outside.length) { return false; }
    for (var i = 0; i < outside.length; i++) {
        if (outside[i] != inside[i]) { 
            return false;
        }
    }
    return true;
}

MirrorDom.Util.node_at_path = function(root, ipath) {
    var node = root;
    for (var i=0; i < ipath.length; i++) {
        node = MirrorDom.Util.apply_ignore_nodes(node.firstChild);
        if (node == null) {
            throw new MirrorDom.Util.PathError(root, ipath);
        }
        for (var j=0; j < ipath[i]; j++) {
            node = MirrorDom.Util.apply_ignore_nodes(node.nextSibling);
            if (node == null) {
                throw new MirrorDom.Util.PathError(root, ipath);
            }
        }
    }
    return node;
};

/**
 * Node at upath...these are very similar to ipaths except
 * they contain directives to continue descending in iframes.
 *
 * The "u" stands for universal. I'm not sure what the "i" stands for, i'll
 * think of something soon.
 *
 * e.g. [1,4,3,'i',1,1,2]  means
 * - iframe at position 1,4,3
 * - inside that iframe, the node at 1,1,2
 *
 * @param doc       Document object (preferably not an actual DOM element in
 *                  the document)
 *
 * @returns         DOM node (if last item in path is 'i', then iframe element)
 */
MirrorDom.Util.node_at_upath = function(doc, upath) {
    var node = doc;
    var in_iframe = false;

    for (var i=0; i < upath.length; i++) {
        switch (upath[i]) {
            case 'm':
                // Special case: Should be the root of the main frame document
                // Ignore this and keep proceeding.
                if (node.nodeName.toLowerCase() == "iframe") {
                    in_iframe = true;
                }
                break;
            case 'i':
                // Descend into iframe - root at this point should be an
                // iframe, otherwise we got a problem
                //var d = MirrorDom.Util.get_document_object_from_iframe(node);
                //node = d;
                if (node.nodeName.toLowerCase() != 'iframe') {
                    throw new Error("Should be in iframe but not, instead got: " + node.nodeName);
                }
                in_iframe = true;
                break;
            default:
                // Descend from document object
                if (in_iframe) {
                    var d = MirrorDom.Util.get_document_object_from_iframe(node);
                    node = d.documentElement;
                    in_iframe = false;
                }

                // should be a number
                node = MirrorDom.Util.apply_ignore_nodes(node.firstChild);
                for (var j=0; j < upath[i]; j++) {
                    node = MirrorDom.Util.apply_ignore_nodes(node.nextSibling);
                }
                break;
        }
    }

    return node;
};



/**
 * Print a string representation of a node
 */
MirrorDom.Util.describe_node = function(node) {
    var desc = [];
    desc.push("<", node.nodeName);
    if (node.id) { desc.push(" #", node.id); }
    if (node.className) { desc.push(' class="', node.className, '"'); }
    desc.push(">");
    return desc.join("")
}


/**
 * Debug utility, returns a string describing the node path
 */
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

/**
 * Debug utility, returns a string describing the upath
 */
MirrorDom.Util.describe_node_at_upath = function(root, upath) {
    var node = root;
    var terminate = false;
    var path_desc = [];
    var parts_desc = [];
    for (var i=0; i < upath.length; i++) {
        switch (upath[i]) {
            case 'm':
                // Special case: Should be the root of the main frame document
                // Ignore this and keep proceeding.
                if (node.nodeName.toLowerCase() != 'iframe') {
                    var d = MirrorDom.Util.get_document_object_from_iframe(node);
                    node = d.documentElement;
                    path_desc.push("m: Descending into main iframe");
                } else {
                    path_desc.push("m: Ignoring");
                }
                break;
            case 'i':
                // Descend into iframe - root at this point should be an
                // iframe, otherwise we got a problem
                var d = MirrorDom.Util.get_document_object_from_iframe(node);
                node = d.documentElement;
                path_desc.push("i: Descending into iframe");
                break;
            default:
                // should be a number
                parts_desc = [];
                node = MirrorDom.Util.apply_ignore_nodes(node.firstChild);
                for (var j=0; j <= upath[i]; j++) {
                    if (j != 0) {
                        node = MirrorDom.Util.apply_ignore_nodes(node.nextSibling);
                    }
                    if (node == null) {
                        item_desc = [j, ": ", "null :("];
                        parts_desc.push(item_desc.join(""));
                        terminate = true;
                        break;
                    } else {
                        item_desc = [j, ": ", MirrorDom.Util.describe_node(node)];
                        parts_desc.push(item_desc.join(""));
                    }
                }
                path_desc.push(parts_desc.join(" -> "));
                break;
        }
        if (terminate) {
            break;
        }
    }
    return path_desc.join("\n");
}


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
