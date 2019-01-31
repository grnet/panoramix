import Component from '@ember/component';
import { argument } from '@ember-decorators/argument';
import { computed } from '@ember-decorators/object';
import { A } from '@ember/array';


const allPaths = A([]);
allPaths.includes = function() { return true; }

export default class ElectionViewComponent extends Component {
  @argument stages;
  @argument user;
  @argument expandedPaths;
  @argument actionDisabled;
  @argument('action') docAction;
  @argument('action') onValueChange;
  @argument('action') onKeyLock;
  @argument('action') expandPath;
  @argument('action') collapsePath;
  @argument('action') showStatus;

  allPaths = allPaths;
}
