# -*- coding: utf-8 -*-

# Copyright (c) 2021 Future Internet Consulting and Development Solutions S.L.

# This file is part of BAE NGSI Dataset plugin.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import os
import  requests

from  datetime import  datetime

from wstore.asset_manager.resource_plugins.plugin import Plugin
from wstore.asset_manager.resource_plugins.exeption import PluginError


API_URL = os.getenv('COATRACK_URL', 'https://integration.coatrack.eu/public-api/services')

UNITS = [{
    'name': 'Api call',
    'description': 'The final price is calculated based on the number of calls made to the API'
}]

class CoatRackService(Plugin):

    def __init__(self):
        self._units = UNITS

    def on_post_product_spec_validation(self, provider, asset):
        # Validate that the provider is authorized to offer the service
        service_id = asset.meta_info['service_id']
        url = API_URL + '/{}/{}'.format(provider.username, service_id)

        response = requests.get(url, headers={
            'Authorization': 'bearer ' + provider.userprofile.access_token
        })

        if response.status_code != 200:
            raise PluginError('You are not authorized to publish such service')

    def on_post_product_offering_validation(self, asset, product_offering):
        # Validate that the pay-per-use model (if any) is supported by the backend
        if 'productOfferingPrice' in product_offering:
            supported_units = [unit['name'].lower() for unit in self._units]

            for price_model in product_offering['productOfferingPrice']:
                if price_model['priceType'] == 'usage':

                    if price_model['unitOfMeasure'].lower() not in supported_units:
                        raise PluginError('Unsupported accounting unit ' +
                                          price_model['unit'] + '. Supported units are: ' + ','.join(supported_units))

    def on_product_acquisition(self, asset, contract, order):
        service_id = asset.meta_info['service_id']
        url = API_URL + '/{}/{}/subscriptions'.format(order.provider.username, service_id)

        response = requests.post(url, headers={
            'Authorization': 'bearer ' + order.customer.userprofile.access_token
        })

    def get_usage_specs(self):
        return self._units

    def get_pending_accounting(self, asset, contract, order):
        accounting = []
        last_usage = None
        if 'pay_per_use' in contract.pricing_model:
            if contract.last_usage is not None:
                start_at = unicode(contract.last_usage.isoformat()).replace(' ', 'T') + 'Z'
            else:
                # The maximum time between refreshes is 30 days, so in the worst case
                # consumption started 30 days ago
                start_at = unicode((datetime.utcnow() - timedelta(days=31)).isoformat()).replace(' ', 'T') + 'Z'

            # Retrieve pending usage
            last_usage = datetime.utcnow()
            end_at = unicode(last_usage.isoformat()).replace(' ', 'T') + 'Z'
            url = API_URL + '/{}/{}/usageStatistics?dateFrom={}&dateUntil={}'.format(
                order.provider.username, asset.meta_info['service_id'], start_at, end_at)

            response = requests.get(url, headers={
                'Authorization': 'bearer ' + order.provider.userprofile.access_token
            })
            usage = response.json()
            accounting.append({
                'unit': 'Api call',
                'value': usage['numberOfCalls'],
                'date': unicode(last_usage.isoformat()).replace(' ', 'T') + 'Z'
            })

        return accounting, last_usage
