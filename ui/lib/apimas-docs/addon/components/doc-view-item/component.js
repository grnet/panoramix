import Component from '@ember/component';
import template from './template';
import { layout, tagName, className, classNames } from '@ember-decorators/component';
import { computed } from '@ember-decorators/object';

@layout(template)
@tagName('li')
@classNames('doc-item')
export default class DocViewItemComponent extends Component {
  @className
  @computed('expanded', 'depth')
  get depthClass() {
    let depth = this.depth > 2 ? `nested nested-${this.depth-2}` : ''
    let expanded = this.isDoc && this.expanded ? 'expanded' : '';
    return depth + ' ' + expanded;
  }

  @className
  @computed('analysis.label')
  get analysisLabel() {
    let label = this.analysis && this.analysis.label;
    if (this.completed) { return 'status-completed'; }
    if (label) { return `status-${label}`; }
    return ''
  }
}
