output "external_ip" {
  value = google_compute_address.external.address
}

output "instance_id" {
  value = google_compute_instance.node.instance_id
}

output "gcp_user_name" {
  value = split("@", data.google_client_openid_userinfo.me.email)[0]
}
