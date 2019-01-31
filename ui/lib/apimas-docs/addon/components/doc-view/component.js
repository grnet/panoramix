import Component from '@ember/component';
import template from './template';
import { layout, tagName, classNames } from '@ember-decorators/component';
import { action, computed } from '@ember-decorators/object';
import { reads, gt, intersect, equal } from '@ember-decorators/object/computed';
import { typeOf } from '@ember/utils';
import { argument } from '@ember-decorators/argument';


@tagName('ul')
@layout(template)
@classNames('doc-view')
export default class DocViewComponent extends Component {
  @argument doc;
  @argument root = '';
  @argument key = null;
  @argument itemTagName = 'div';
  @argument docTagName = 'div';
  @argument itemComponent = 'doc-view-item';
  @argument docComponent = 'doc-view';
  @argument expandedPaths = [];
  @argument meta = {};
  @argument completed = false;

  @argument('action') onExpand = function() {};
  @argument('action') onCollapse = function() {};
  @argument('action') onItemClick = function() {};
  @argument('action') onValueChange = function() {};
  @argument('action') onKeyLock = function() {};

  @computed('doc')
  get docType() { return typeOf(this.doc); }

  @computed('path')
  get pathParts() { return this.path.split('/'); }
  @reads('pathParts.length') depth;

  @computed('root', 'key')
  get path() { if (!this.key) { return '' } return this.root + '/' + this.key; }

  @computed('keys.[]')
  get items() {
    return this.keys.map((key) => {
      let value = this.doc[key];
      let type = typeOf(value);
      let isDoc = (type == 'object' || type == 'array');
      let path = [this.path, key].join('/')
      let root = this.path
      return {key, value, isDoc, path, root, type};
    })
  }

  @computed('items.[]', 'expandedPaths.[]')
  get expandedItems() {
    let paths = this.expandedPaths;
    return this.items.filter(({ path }) => { return paths.includes(path); })
  }

  @computed('keys.[]', 'path')
  get paths() {
    return this.keys.map((key) => { return [this.path, key].join('/'); })
  }

  @intersect('paths', 'expandedPaths') selfExpandedPaths;
  @equal('selfExpandedPaths.length', 0) canExpandAll;

  @computed('doc', 'docType')
  get keys() {
    if (this.docType == 'object') {
      return Object.keys(this.doc);
    } else if (this.docType == 'array') {
      return Object.keys(this.doc);
    } else {
      return [];
    }
  }
  set keys(val) { return val }

  didReceiveAttrs() {
    this._super(...arguments);
    if (this.isDoc) {
      let newKeys = Object.keys(this.doc);
      if (newKeys.len != this.keys) {
        this.keys.setObjects(newKeys);
      }
    }
  }

  @gt('keys.length', 0) isDoc;


  @action expandPath(path=null) {
    if (!this.onExpand) { return }
    if (!path) { path = this.path }
    this.onExpand(path);
  }

  @action collapsePath(path=null) {
    if (!this.onCollapse) { return }
    if (!path) { path = this.path }
    this.onCollapse(path);
  }
}
