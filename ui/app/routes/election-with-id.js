import Route from '@ember/routing/route';

export default Route.extend({
  redirect(transition) {
    let user = this.paramsFor('election_with_id').user || 'trustee1';
    this.transitionTo('election', user);
  }
});

