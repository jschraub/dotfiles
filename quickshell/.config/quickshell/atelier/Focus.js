.pragma library
.import QtQuick 2.15 as Quick

// Only inspect the active panel, never the desktop or authentication windows.
function controls(item) {
    if (!item || !item.visible || !item.enabled) return [];
    let result = [];
    if ((item.focusPolicy !== undefined && (item.focusPolicy & Qt.TabFocus)) || item.activeFocusOnTab)
        result.push(item);
    for (const child of item.children || []) result = result.concat(controls(child));
    return result;
}

function reveal(item) {
    for (let parent = item ? item.parent : null; parent; parent = parent.parent) {
        if (typeof parent.contentY !== "number" || !parent.contentItem) continue;
        const point = item.mapToItem(parent.contentItem, 0, 0);
        let y = parent.contentY;
        if (point.y < y) y = point.y;
        else if (point.y + item.height > y + parent.height) y = point.y + item.height - parent.height;
        parent.contentY = Math.max(0, Math.min(Math.max(0, parent.contentHeight - parent.height), y));
    }
}

function first(item) {
    const candidates = controls(item);
    if (!candidates.length) return false;
    candidates[0].forceActiveFocus(Qt.TabFocusReason);
    return true;
}

function cycle(panel, current, forward) {
    const candidates = controls(panel);
    if (!candidates.length) return;
    let owner = current;
    while (owner && candidates.indexOf(owner) < 0) owner = owner.parent;
    const index = candidates.indexOf(owner);
    const next = index < 0 ? (forward ? 0 : candidates.length - 1)
        : (index + (forward ? 1 : -1) + candidates.length) % candidates.length;
    candidates[next].forceActiveFocus(Qt.TabFocusReason);
    reveal(candidates[next]);
}

function row(view, index) {
    if (!view || view.count === 0) return;
    const direction = index >= view.currentIndex ? 1 : -1;
    view.currentIndex = Math.max(0, Math.min(view.count - 1, index));
    view.positionViewAtIndex(view.currentIndex, Quick.ListView.Contain);
    Qt.callLater(function() {
        const next = view.currentIndex + direction;
        if (!first(view.currentItem) && next >= 0 && next < view.count) row(view, next);
    });
}
