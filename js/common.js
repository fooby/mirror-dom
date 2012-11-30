var MirrorDom = MirrorDom === undefined ? {} : MirrorDom;

// ============================================================================
// Misc
// ============================================================================

/**
 * Convert array to object for fast hashmap lookup
 *
 * @param <variable length>     Either strings or list of strings       
 */
MirrorDom.to_set = function() {
    var result = {};
    for (var i = 0; i < arguments.length; i++) {
        var x = arguments[i];
        if (x instanceof Array) {
            for (var j = 0; j < x.length; j++) { result[x[j]] = null; }
        } else {
            result[x] = null;
        }
    }
    return result;
};

// ============================================================================
// Doctype
// ============================================================================
MirrorDom.HTML_NAMESPACE = 'http://www.w3.org/1999/xhtml';
MirrorDom.SVG_NAMESPACE = 'http://www.w3.org/2000/svg';
MirrorDom.VML_NAMESPACE = 'urn:schemas-microsoft-com:vml';

MirrorDom.determine_node_doc_type = function(node) {
    // Text node needs to reference parent
    var n = (node.nodeType == 3) ? node.parentNode : node;
    switch (n.namespaceURI) {
        case MirrorDom.HTML_NAMESPACE:
            return 'html';
        case MirrorDom.SVG_NAMESPACE:
            return 'svg';
        default:
            // VML hack, sigh
            // .xmlns seems to be defined with inline xmlns attribute.
            // .tagUrn seems to be defined with namespace prefix
            if ((n.xmlns != undefined && n.xmlns == MirrorDom.VML_NAMESPACE) ||
               (n.tagUrn != undefined && n.tagUrn == MirrorDom.VML_NAMESPACE)) {
                return 'vml';
            }

            return 'html';
    }
};

// ============================================================================
// Properties
// ============================================================================

// Set of ALL properties in a given document type.
MirrorDom.PROPERTY_NAMES = {
    'html': ['disabled', 'value', 'checked', 'style.cssText', 'className',
             'colSpan', 'selectedIndex'],
    'svg': ['style.cssText'],
    'vml': ['style.cssText', 'runtimeStyle.cssText', 'path.v',
            'strokeColor.value', 'strokeweight']
};

// Restrict certain properties to certain tags. Must be in lower case
MirrorDom.PROPERTY_RESTRICT = {
    'html': { 'colSpan': MirrorDom.to_set('td', 'th'),
              'value': MirrorDom.to_set('input'),
              'selectedIndex': MirrorDom.to_set('select') },
    'vml': { 'path.v': MirrorDom.to_set('shape') }
};

// Cache of doc_type -> tag_name -< lookup
MirrorDom.PROPERTY_LOOKUP_CACHE = {};

/**
 * Returns a property lookup list for a given node.
 *
 * e.g. [['style.cssText', ['style', 'cssText']], ['disabled', 'disabled']]
 *
 * The property_key can be used for storing in a flat dictionary, while the
 * property_key_component_lookup allows to descend through nested objects to
 * retrieve/set the value.
 *
 * @return {Array} of [property_key, [property_split_components]].
 */
MirrorDom.get_property_list = function(node) {
    // Only interested in Element node properties
    if (node.nodeType != 1) { return null; }
    var doc_type = MirrorDom.determine_node_doc_type(node);
    var tag_name = node.tagName.toLowerCase();
    // Check cache
    var cached = MirrorDom.PROPERTY_LOOKUP_CACHE;
    if (cached[doc_type] && cached[doc_type][tag_name]) {
        return cached[doc_type][tag_name];
    }
    // Begin generate new filtered lookup list
    var properties = MirrorDom.PROPERTY_NAMES[doc_type];
    if (properties == undefined) {
        throw new Error('Unexpected doctype for property lookup: ' + doc_type);
    }
    var restrict = MirrorDom.PROPERTY_RESTRICT[doc_type];
    var result = [];
    for (var i = 0; i < properties.length; i++) {
        var p = properties[i];
        if (restrict && restrict[p] && !(tag_name in restrict[p])) { continue; }
        result.push([p, p.split('.')]);
    }
    if (cached[doc_type] == undefined) { cached[doc_type] = {}; }
    cached[doc_type][tag_name] = result;
    return result;
};

/**
 * Set property on a DOM node.
 *
 * @param {node} node           DOM or cloned node (see clone_node).
 *
 * @param {array} prop_lookup   An object attribute path
 *                              e.g. ["style", "cssText"].
 *
 * @param {boolean} force       Force create arbitrary objects to ensure the
 *                              path gets set (don't use on actual DOM nodes).
 */
MirrorDom.set_property = function(node, prop_lookup, value, force) {
    var i;
    var prop = node;
    for (i = 0; i < prop_lookup.length - 1; i++) {
        if (!(prop_lookup[i] in prop)) {
            if (force) {
                prop[prop_lookup[i]] = {};
            } else {
                return; // Nope, couldn't proceed
            }
        }
        prop = prop[prop_lookup[i]];
    }
    prop[prop_lookup[i]] = value;
};

/**
 * Retrieve property from a DOM node.
 *
 * @param {node} node           DOM node or cloned node.
 * @param {array} prop_lookup   An object attribute path
 *                              e.g. ["style", "cssText"].
 * @return {array}             [success, value].
 */
MirrorDom.get_property = function(node, prop_lookup) {
    var prop = node;
    for (var i = 0; i < prop_lookup.length; i++) {
        if (prop_lookup[i] in prop) {
            prop = prop[prop_lookup[i]];
        } else {
            return [false, null];
        }
    }
    return [true, prop];
};

MirrorDom.get_properties = function(node) {
    var property_list = MirrorDom.get_property_list(node);
    if (property_list == null) {
        return null;
    }
    var new_props = {};
    var found = false;
    for (var i = 0; i < property_list.length; i++) {
        var prop_text = property_list[i][0];
        var prop_lookup = property_list[i][1];
        var prop_result = MirrorDom.get_property(node, prop_lookup);
        var prop_found = prop_result[0];
        var prop_value = prop_result[1];
        if (prop_found && (prop_value != '' && prop_value != null)) {
            new_props[prop_text] = prop_value;
            found = true;
        }
    }
    return found ? new_props : null;
};

// ============================================================================
// Iframes
// ============================================================================
/**
 * @param {node} iframe      Iframe element.
 */
MirrorDom.get_iframe_document = function(iframe) {
    var d = null;
    if (iframe) {
        // Retrieve iframe document
        if (iframe.contentDocument) {
            d = iframe.contentDocument; // Firefox
        } else if (iframe.contentWindow) {
            d = iframe.contentWindow.document; // IE
        } else {
            // Something went very wrong
            throw new Error('Could not retrieve IFrame document.');
        }
    } else {
        throw new Error('IFrame is null');
    }
    return d;
};

// ============================================================================
// DOM helpers
// ============================================================================

/**
 * Add sibling node to the right of target
 */
MirrorDom.insert_after = function(new_node, target) {
    target.parentNode.insertBefore(new_node, target.nextSibling);
};

// ============================================================================
// Attributes
// ============================================================================


// Ignore certain attributes when doing attribute comparison
MirrorDom.IGNORE_ALL_ATTRIBS = MirrorDom.to_set('style');
MirrorDom.IGNORE_ATTRIBS = {
    'html': { 'src': MirrorDom.to_set('iframe') }
};

/**
 * Determine if we should skip attribute
 */
MirrorDom.should_ignore_attribute = function(node, attribute) {
    if (attribute in MirrorDom.IGNORE_ALL_ATTRIBS) { return true; }

    var doc_type = MirrorDom.determine_node_doc_type(node);
    var ignore = MirrorDom.IGNORE_ATTRIBS[doc_type];
    var nodeName = node.nodeName.toLowerCase();
    if (ignore && ignore[attribute] && nodeName in ignore[attribute]) {
        return true;
    }
    return false;
};

// ============================================================================
// Tags
// ============================================================================
MirrorDom.IGNORE_NODES = MirrorDom.to_set('META', 'SCRIPT', 'TITLE');
MirrorDom.ACCEPT_HTML_NODES = MirrorDom.to_set('BODY', 'HEAD');

/**
 * Determines if the current DOM node is an interesting element.
 */
MirrorDom.should_ignore_node = function(node) {
    if (node.nodeType != 1) { return true; }
    if (node.nodeName in MirrorDom.IGNORE_NODES) { return true; }
    if (node.parentNode.nodeName == 'HTML' &&
            !(node.nodeName in MirrorDom.ACCEPT_HTML_NODES)) {
        return true;
    }
    return false;
};

// ============================================================================
// Traversal
// ============================================================================
/**
 * Iterate through nextSibling until we get the next interesting element.
 * Note: If the provided node is interesting, returns that straight away.
 *
 * @param {node} node       Node from which we start iterating.
 */
MirrorDom.next_element = function(node) {
    while (node != null && MirrorDom.should_ignore_node(node)) {
        node = node.nextSibling;
    }
    return node;
};


/**
 * zero based, so not REALLY nth child.
 *
 * Note: This is designed to return undefined if pos is the index AFTER the
 * last child in the node (or if index is 0 and node has no children)
 *
 * @param {node} node       Node to retrieve the child from.
 * @param {int} pos         Position of child.
 */
MirrorDom.nth_child = function(node, pos) {
    var n = MirrorDom.next_element(node.firstChild);
    for (var i = 1; i <= pos; i++) {
        n = MirrorDom.next_element(n.nextSibling);
    }
    return n;
};

/**
 *  Retrieve sequential text node content until the next element.
 *
 *  Note: Due to the way this is invoked, if node is an interesting element
 *  as determined by should_ignore_node(), then immediately abort with no text
 *  returned.
 *
 *  @param {node} node      Start element from which to start scanning for
 *                          sequential text nodes.
 */
MirrorDom.get_text_node_content = function(node) {
    var text = [];
    node = MirrorDom.next_text_node(node);
    while (node != null) {
        text.push(node.nodeValue);
        node = MirrorDom.next_text_node(node.nextSibling);
    }
    return text.join('');
};

/**
 * Loops to next sequential text node.
 *
 * Note: If passed a text node, will return the text node immediately.
 */
MirrorDom.next_text_node = function(node) {
    while (node != null) {
        if (!MirrorDom.should_ignore_node(node)) {
            return null;
        } else if (node.nodeType == 3) {
            return node;
        }
        node = node.nextSibling;
    }
    return node;
};

// ============================================================================
// Node processing
// ============================================================================

/**
 * Get node OuterHTML
 *
 * http://stackoverflow.com/questions/1700870/how-do-i-do-outerhtml-in-firefox
 */
MirrorDom.outerhtml = function(node) {
    if (node.outerHTML !== undefined) {
        return node.outerHTML;
    }
    var div = document.createElement('div');
    div.appendChild(node.cloneNode(true));
    return div.innerHTML;
};

// ============================================================================
// XML
// ============================================================================

/**
 * We've got an XML document, and we need to manually construct the nodes and
 * chuck it into the DOM.
 *
 * @param {document} doc       Document to which the copy belongs.
 * @param {node} root          XML node root.
 */
MirrorDom.copy_xml_node_to_dom = function(doc, root) {
    function copy_node(node) {
        switch (node.nodeType) {
            case 1:
                var elem = doc.createElement(node.tagName);
                for (var i = 0; i < node.attributes.length; i++) {
                    var attrib = node.attributes[i];
                    elem.setAttribute(attrib.name, attrib.value);
                }
                return elem;
            case 8:
                var comment = doc.createComment(node.textContent);
                return comment;
            case 3:
                var text = doc.createTextNode(node.nodeValue);
                return text;
            default:
                // hmm
        }
    }
    function append_child(parent_node, child_node) {
        try {
            parent_node.appendChild(child_node);
            return true;
        } catch (e) {
            // IE8 HACK: appendChild on <style> or <script> elements don't work:
            // We get "Unexpected call to method or property access"
            if (e.number == -2147418113 && (parent_node.nodeName == 'SCRIPT' ||
                        parent_node.nodeName == 'STYLE')) {
                return false; // We'll just skip this bit I guess
            }
            throw e;
        }
    }
    return MirrorDom.copy_dom_node_tree(doc, root, copy_node, append_child);
};

/**
 * Iterate through an XML document and replicate the nodes on the dom node.
 *
 * @param {node} doc                The XML document to copy from.
 * @param {node} root               The DOM node to copy to.
 * @param {function} copy_func      Function which takes XML node and returns
 *                                  target DOM node.
 * @param {function} append_func    Function which can append the node to the
 *                                  DOM node.
 */
MirrorDom.copy_dom_node_tree = function(doc, root, copy_func, append_func) {
    var node = root;
    var out_root = copy_func(root);
    var out_node = out_root;

    // Default append child function: call node's appendChild
    if (append_func == undefined) {
        append_func = function(p, c) {
            p.appendChild(c);
            return true;
        };
    }

    // This is similar to broadcaster's clone node, actually
    while (true) {
        if (node.firstChild) {
            var child = copy_func(node.firstChild);
            var success = append_func(out_node, child);

            // Hack because in IE8, some elements don't allow appendChild.
            if (success) {
                node = node.firstChild;
                out_node = child;
            } else {
                // Welp, error condition
                break;
            }

        } else if (node === root) {
            return out_root;
        } else if (node.nextSibling) {
            var sibling = copy_func(node.nextSibling);
            append_func(out_node.parentNode, sibling);
            node = node.nextSibling;
            out_node = sibling;
        } else {
            while (!node.nextSibling) {
                node = node.parentNode;
                out_node = out_node.parentNode;
                if (node === root) {
                    return out_root;
                }
            }
            var sibling = copy_func(node.nextSibling);
            append_func(out_node.parentNode, sibling);
            node = node.nextSibling;
            out_node = sibling;
        }
    }

    // unreachable except in error condition
    return out_root;
};

// ============================================================================
// SVG
// ============================================================================

/**
 * @param {svgdoc} svg_doc      SVGDocument to which this belongs (null if
 *                              node_xml is the actual SVG document).
 *
 * @param {string} node_xml     XML fragment.
 */
MirrorDom.to_svg = function(svg_doc, node_xml) {
    var parser = new DOMParser();
    var parsed_svg = parser.parseFromString(node_xml, 'image/svg+xml');
    // Note: Using document only works if node_xml contains a complete SVG
    // docoument.
    var d = svg_doc || document;
    function copy_svg_node(node) {
        switch (node.nodeType) {
            case 1:
                var elem = d.createElementNS(MirrorDom.SVG_NAMESPACE,
                        node.tagName);
                for (var i = 0; i < node.attributes.length; i++) {
                    var attrib = node.attributes[i];
                    var ns = attrib.namespaceURI || null;
                    elem.setAttributeNS(ns, attrib.name, attrib.value);
                }
                return elem;
            case 3:
                var text = d.createTextNode(node.textContent);
                return text;
            default:
                // hmm
        }
    }

    return MirrorDom.copy_dom_node_tree(d, parsed_svg.documentElement,
            copy_svg_node);
};

/**
 * ============================================================================
 * Errors
 * ============================================================================
 */
MirrorDom.PathError = function(root, path) {
    this.name = 'PathError';
    this.root = root;
    this.path = path;
    this.message = 'Couldn\'t retrieve path ' + path.join(',') +
        ' for node ' + MirrorDom.describe_node(root);
};

MirrorDom.PathError.prototype.describe_path = function() {
    return MirrorDom.describe_path(this.root, this.path);
};

MirrorDom.DiffError = function(diff, root, path) {
    this.name = 'PathError';
    this.diff = diff;
    this.root = root;
    this.path = path;
    this.message = 'Couldn\'t apply diff [' + diff.join(',') +
        '] for node ' + MirrorDom.describe_node(root) + ', path ' +
        path.join(',');
};

MirrorDom.DiffError.prototype.describe_path = function() {
    return MirrorDom.describe_path(this.root, this.path);
};

/**
 * ============================================================================
 * Path Utilities
 * ============================================================================
 */

MirrorDom.path_equal = function(x, y) {
    if (x.length != y.length) { return false; }
    for (var i = 0; i < x.length; i++) {
        if (x[i] != y[i]) { return false; }
    }
    return true;
};

/**
 * Returns true if "inside" is equal to or a child of "outside"
 *
 * e.g. [1,2,4,5,6], [1,2,4] = true
 *
 * Note that "outside" should be the SHORTER path (shorter means higher up)
 */
MirrorDom.is_inside_path = function(inside, outside) {
    if (inside.length < outside.length) { return false; }
    for (var i = 0; i < outside.length; i++) {
        if (outside[i] != inside[i]) {
            return false;
        }
    }
    return true;
};

MirrorDom.node_at_path = function(root, ipath) {
    var node = root;
    for (var i = 0; i < ipath.length; i++) {
        node = MirrorDom.next_element(node.firstChild);
        if (node == null) {
            throw new MirrorDom.PathError(root, ipath);
        }
        for (var j = 0; j < ipath[i]; j++) {
            node = MirrorDom.next_element(node.nextSibling);
            if (node == null) {
                throw new MirrorDom.PathError(root, ipath);
            }
        }
    }
    return node;
};

/**
 * Node at framepath...these are very similar to ipaths except
 * they contain directives to continue descending in iframes.
 *
 * The "u" stands for universal. I'm not sure what the "i" stands for, i'll
 * think of something soon.
 *
 * e.g. [1,4,3,'i',1,1,2]  means
 * - iframe at position 1,4,3
 * - inside that iframe, the node at 1,1,2
 *
 * @param {document} doc    Document object (preferably not an actual DOM
 *                          element in the document).
 *
 * @return {node}           DOM node (if last item in path is 'i', then iframe
 *                          element).
 */
MirrorDom.node_at_framepath = function(doc, framepath) {
    var node = doc;
    var in_iframe = false;

    for (var i = 0; i < framepath.length; i++) {
        switch (framepath[i]) {
            case 'm':
                // Special case: Should be the root of the main frame document
                // Ignore this and keep proceeding.
                if (node.nodeName.toLowerCase() == 'iframe') {
                    in_iframe = true;
                }
                break;
            case 'i':
                // Descend into iframe - root at this point should be an
                // iframe, otherwise we got a problem
                //var d = MirrorDom.get_iframe_document(node);
                //node = d;
                if (node.nodeName.toLowerCase() != 'iframe') {
                    throw new Error('Should be in iframe but got' +
                            node.nodeName + ' instead.');
                }
                in_iframe = true;
                break;
            default:
                // Descend from document object
                if (in_iframe) {
                    var d = MirrorDom.get_iframe_document(node);
                    node = d.documentElement;
                    in_iframe = false;
                }

                // should be a number
                node = MirrorDom.next_element(node.firstChild);
                for (var j = 0; j < framepath[i]; j++) {
                    node = MirrorDom.next_element(node.nextSibling);
                }
                break;
        }
    }

    return node;
};



/**
 * Print a string representation of a node
 */
MirrorDom.describe_node = function(node) {
    var desc = [];
    desc.push('<', node.nodeName);
    if (node.id) { desc.push(' #', node.id); }
    if (node.className) { desc.push(' class="', node.className, '"'); }
    desc.push('>');
    return desc.join('');
};


/**
 * Debug utility, returns a string describing the node path
 */
MirrorDom.describe_path = function(root, ipath) {
    var node = root;
    var path_desc = [];
    var terminate = false;

    for (var i = 0; i < ipath.length; i++) {
        var item_desc = [];
        var line_desc = [];

        node = MirrorDom.next_element(node.firstChild);
        for (var j = 0; j <= ipath[i]; j++) {
            if (j != 0) {
                node = MirrorDom.next_element(node.nextSibling);
            }
            if (node == null) {
                item_desc = [j, ': ', 'null :('];
                line_desc.push(item_desc.join(''));
                terminate = true;
                break;
            } else {
                item_desc = [j, ': ', MirrorDom.describe_node(node)];
                line_desc.push(item_desc.join(''));
            }
        }

        path_desc.push(line_desc.join(' -> '));

        if (terminate) {
            break;
        }
    }
    return path_desc.join('\n');
};

/**
 * Debug utility, returns a string describing the framepath
 */
MirrorDom.describe_framepath = function(root, framepath) {
    var node = root;
    var terminate = false;
    var path_desc = [];
    var parts_desc = [];
    for (var i = 0; i < framepath.length; i++) {
        switch (framepath[i]) {
            case 'm':
                // Special case: Should be the root of the main frame document
                // Ignore this and keep proceeding.
                if (node.nodeName.toLowerCase() == 'iframe') {
                    var d = MirrorDom.get_iframe_document(node);
                    node = d.documentElement;
                    path_desc.push('m: Descending into main iframe');
                } else {
                    path_desc.push('m: Ignoring');
                }
                break;
            case 'i':
                // Descend into iframe - root at this point should be an
                // iframe, otherwise we got a problem
                var d = MirrorDom.get_iframe_document(node);
                node = d.documentElement;
                path_desc.push('i: Descending into iframe');
                break;
            default:
                // should be a number
                parts_desc = [];
                node = MirrorDom.next_element(node.firstChild);
                for (var j = 0; j <= framepath[i]; j++) {
                    if (j != 0) {
                        node = MirrorDom.next_element(node.nextSibling);
                    }
                    if (node == null) {
                        item_desc = [j, ': ', 'null :('];
                        parts_desc.push(item_desc.join(''));
                        terminate = true;
                        break;
                    } else {
                        item_desc = [j, ': ', MirrorDom.describe_node(node)];
                        parts_desc.push(item_desc.join(''));
                    }
                }
                path_desc.push(parts_desc.join(' -> '));
                break;
        }
        if (terminate) {
            break;
        }
    }
    return path_desc.join('\n');
};

MirrorDom.is_main_framepath = function(framepath) {
    return (framepath.length == 1 && framepath[0] == 'm');
};
