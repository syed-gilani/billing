# app level
$username = "worker-dev"
$app = "billing"
$env = "dev"

host::app_user {'appuser':
    app        => $app,
    env        => $env,
    username   => $username,
}

host::aws_standard_packages {'std_packages':}
host::wsgi_setup {'wsgi':}
require host::hosts_file

package { 'postgresql93':
    ensure  => installed
}
package { 'postgresql93-devel':
    ensure  => installed
}
# TODO: can we remove these?
package { 'html2ps':
    ensure  => installed
}
package { 'libevent-dev':
    ensure  => installed
}
file { "/home/${username}/logs":
    ensure      => directory,
    owner       => $username,
    group       => $username,
}

file { "/etc/init/billing-${env}-exchange.conf":
ensure => file,
content => template('conf/billing-exchange.conf.erb')
}

file { "/etc/init/billentry-${env}-exchange.conf":
ensure => file,
content => template('conf/billentry-exchange.conf.erb')
}

rabbit_mq::rabbit_mq_server {'rabbit_mq_server':
    cluster => 'rabbit@ip-10-0-0-158'
}

rabbit_mq::user_permission {'guest':
    vhost => $env,
    conf  => '.*',
    write  => '.*',
    read  => '.*',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server'], Rabbit_mq::Vhost[$env]],
}

rabbit_mq::vhost {$env:
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server']]
}

rabbit_mq::policy {'HA':
    pattern => '.*',
    vhost => $env,
    policy => '{"ha-sync-mode":"automatic", "ha-mode":"all", "federation-upstream-set":"all"}',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server'], Rabbit_mq::Vhost[$env]]
}