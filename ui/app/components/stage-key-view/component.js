import Component from 'apimas-docs/components/doc-view-item/component';
import { argument } from '@ember-decorators/argument';
import { classNames, tagName, layout, attribute } from '@ember-decorators/component';
import { action, computed } from '@ember-decorators/object';
import template from './template';

@tagName('')
@layout(template)
export default class StageKeyViewItemComponent extends Component {

  constructor() {
    super(...arguments);
    this.classNameBindings = [];
    this.attributeBindings = [];
  }

  @attribute role = "listitem";
  @attribute tabindex = "-1";

  @argument root;
  @argument path;
  @argument key;
  @argument doc;
  @argument completed;
  @argument analysis;
  @argument disabled;
  @argument isDoc;
  @argument depth;
  @argument expanded;
  @argument meta;
  @argument type;

  @argument('action') expandPath = function() {};
  @argument('action') collapsePath = function() {};
  @argument('action') onClick = function() {};
  @argument('action') onChange = function() {};
  @argument('action') onLock = function() {};
  @argument('action') showStatus = function() {};

  @computed('key', 'meta.key_label')
  get label() {
    let dflt = Ember.String.capitalize(this.key.split('_').join(' '));
    return this.meta && this.meta.key_label || dflt;
  }

  @computed('meta.state_label')
  get stateCls() {
    let cls = this.meta && this.meta.state_label;
    return `state state-${cls}`;
  }

  // this is to decide if raw document value should be displayed
  // when node stage is closed ('done' state)
  @computed('meta.type', 'doc')
  get rawDocView() {
    return !['file'].includes(this.meta.type)
  }
}
